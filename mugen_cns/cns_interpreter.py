# -*- coding: utf-8 -*-
from __future__ import division

"""
cns_interpreter.py
Agnóstico de backend. Orquesta el flujo CNS:
- Estados y cambios de estado (ChangeState/SelfState).
- Evaluación de triggers/expresiones por frame.
- Ejecución de SCTRLs -> llamadas a un adaptador de backend (gráfico/sonoro/físico).
- Pausas (Pause) y SuperPause, transparencia global, recoloreos, explods/helpers, sonidos.

Requisitos del proyecto:
- CNSRuntime de tu cns_integrator (rt) con:
    - rt.eval_ctx (EvalContext)
    - rt.eval_expr(node) -> valor (usa triggers_loader)
    - rt.build_runtime_plan() -> plan por estado
- Los controladores normalizados tienen shape:
    {"name": <canon/degradado>, "params": <dict evaluado o nodo>, "spec": <spec|None>, "raw": <Controller AST>}

Adaptador:
- Provee métodos ctrl_* para cada SCTRL que quieras soportar (ver BaseAdapter).
- Provee hooks on_state_enter, on_after_controllers, render_frame, etc.
- El adaptador no tiene por qué dibujar nada; puede ser “headless” y delegar a otro sistema.
"""

# ---------------- Interface del adaptador (backend) --------------------------

class BaseAdapter(object):
    """
    Implementa esta interfaz en tu backend (Pygame, OpenGL, etc.).
    Los métodos ctrl_* se invocan por nombre de SCTRL (lowercase).
    """

    # ---- Ciclo de vida / hooks ----
    def bind_interpreter(self, interpreter):
        """El intérprete te llama con self para que puedas pedir change_state, etc."""
        self.interpreter = interpreter

    def on_state_enter(self, stateno):
        """Entraste a un nuevo State."""
        pass

    def on_state_exit(self, stateno):
        """Saliste del State actual (antes de entrar a otro)."""
        pass

    def on_after_controllers(self, ctx):
        """Después de ejecutar todos los SCTRLs este frame (aplica física, colisiones, etc.)."""
        pass

    def on_pause(self, frames):
        """Comienza una pausa normal (Pause)."""
        pass

    def on_superpause(self, frames, darken=False, p2defmul=None):
        """Comienza una SuperPause."""
        pass

    def render_frame(self):
        """Dibuja y presenta (si aplica)."""
        pass

    # ---- Utilidades opcionales que el intérprete puede llamar ----
    def request_change_state(self, stateno):
        """Algunos backends prefieren capturar la notificación de cambio de estado aquí."""
        # Por defecto, delega al propio intérprete
        self.interpreter.change_state(stateno)

    # ---- SCTRLs comunes (implementa las que uses) ----
    def ctrl_changestate(self, params, ctx):         pass
    def ctrl_selfstate(self, params, ctx):           pass
    def ctrl_statetypeset(self, params, ctx):        pass

    def ctrl_posadd(self, params, ctx):              pass
    def ctrl_posset(self, params, ctx):              pass
    def ctrl_veladd(self, params, ctx):              pass
    def ctrl_velset(self, params, ctx):              pass
    def ctrl_width(self, params, ctx):               pass

    def ctrl_trans(self, params, ctx):               pass
    def ctrl_palfx(self, params, ctx):               pass
    def ctrl_allpalfx(self, params, ctx):            pass
    def ctrl_envcolor(self, params, ctx):            pass
    def ctrl_remappal(self, params, ctx):            pass

    def ctrl_explod(self, params, ctx):              pass
    def ctrl_modifyexplod(self, params, ctx):        pass
    def ctrl_removeexplod(self, params, ctx):        pass

    def ctrl_helper(self, params, ctx):              pass
    def ctrl_destroyself(self, params, ctx):         pass

    def ctrl_playsnd(self, params, ctx):             pass
    def ctrl_stopsnd(self, params, ctx):             pass
    def ctrl_sndpan(self, params, ctx):              pass

    def ctrl_pause(self, params, ctx):               pass
    def ctrl_superpause(self, params, ctx):          pass

    def ctrl_assertspecial(self, params, ctx):       pass
    def ctrl_sprpriority(self, params, ctx):         pass
    def ctrl_screenbound(self, params, ctx):         pass

    # Fallback genérico si el SCTRL no tiene método específico
    def ctrl_fallback(self, name, params, ctx):
        """Opción: loguear SCTRL no implementado."""
        # print("[Adapter] SCTRL no implementado:", name, params)
        pass


# ---------------- Proveedor de datos para triggers ---------------------------

class _TriggerProvider(object):
    """
    Proveedor mínimo para tus triggers. Amplía según tu catálogo.
    Se alimenta del propio intérprete (pos, vel, tiempos, estados).
    """
    def __init__(self, interp):
        self.i = interp

    # --- tiempo/estado ---
    def time_in_state(self):
        return int(self.i.state_time)

    def state_no(self):
        return int(self.i.current_state_no or 0)

    def prev_state_no(self):
        return int(getattr(self.i, "_prev_state_no", -1))

    # --- control ---
    def has_control(self):
        # Si manejas 'ctrl' en flags/entidad, conéctalo aquí.
        return int(self.i.ctx.get("flags", {}).get("ctrl", 1))

    # --- posición/velocidad (ctx ya guarda pos/vel) ---
    def pos_x(self):
        return float(self.i.ctx["pos"][0])

    def pos_y(self):
        return float(self.i.ctx["pos"][1])

    def vel_x(self):
        return float(self.i.ctx["vel"][0])

    def vel_y(self):
        return float(self.i.ctx["vel"][1])

    # --- salud/vida (ajusta si tienes HP real) ---
    def is_alive(self):
        return 1

    # --- stubs ampliables según tus triggers ---
    # def round_state(self): ...
    # def p2_dist_x(self): ...
    # def p2_dist_y(self): ...
    # def num_explod(self, id=None): ...
    # def anim_no(self): ...
    # def anim_time_left(self): ...
    # def front_edge_dist(self): ...
    # def back_edge_dist(self): ...
    # etc.


# ---------------- Intérprete principal CNS → Backend --------------------------

class CNSInterpreter(object):
    def __init__(self, runtime, backend_adapter, *, honor_triggerall=True):
        """
        runtime: CNSRuntime (ver cns_integrator.py)
        backend_adapter: instancia de BaseAdapter (o subclase)
        honor_triggerall: si True, respeta TriggerAll y trigger1..N del AST si existen
        """
        self.rt = runtime
        self.adapter = backend_adapter or BaseAdapter()
        self.adapter.bind_interpreter(self)

        self.honor_triggerall = honor_triggerall

        # AST/Plan
        self.plan_by_state = {}   # stateno -> [ controllers ]
        self.current_state_no = None
        self.state_time = 0       # ticks transcurridos en el estado actual

        # Pausas
        self.pause_ticks = 0      # Pause normal
        self.superpause_ticks = 0 # SuperPause (puede tener darken/p2defmul)

        # Contexto dinámica mínima (puedes extenderla):
        self.ctx = {
            "vars": {},     # var int
            "fvars": {},    # var float
            "flags": {},    # banderas varias
            "vel": [0.0, 0.0],  # vx, vy
            "pos": [0.0, 0.0],  # x, y
        }

        # ---- Provider + shim de triggers (sin tocar evaluator) ---------------
        # Creamos un provider y "envolvemos" cada impl de trigger para que use
        # este provider aunque el evaluator pase None como primer argumento.
        provider = _TriggerProvider(self)
        self._provider = provider

        try:
            registry = getattr(self.rt, "eval_ctx", None)
            registry = getattr(registry, "triggers", None)
        except Exception:
            registry = None

        if isinstance(registry, dict):
            for _name, spec in list(registry.items()):
                impl = spec.get("impl") if isinstance(spec, dict) else None
                if callable(impl):
                    def _make_wrapped(_impl):
                        def _wrapped(_ignored_ctx, *args):
                            return _impl(provider, *args)
                        return _wrapped
                    spec["impl"] = _make_wrapped(impl)

    # --------- Setup del plan de ejecución -----------------------------------
    def load_plan(self, plan):
        """
        plan: lista devuelta por runtime.build_runtime_plan()
        """
        self.plan_by_state = {e["stateno"]: list(e["controllers"]) for e in (plan or [])}
        # estado inicial: el menor stateno presente (o 0 si existe)
        if self.plan_by_state:
            initial = min(self.plan_by_state.keys())
            self.change_state(initial)

    # --------- Gestión de estados --------------------------------------------
    def change_state(self, stateno):
        if self.current_state_no is not None:
            try:
                self.adapter.on_state_exit(self.current_state_no)
            except Exception:
                pass

        # guarda anterior para triggers que lo pidan
        self._prev_state_no = self.current_state_no

        self.current_state_no = int(stateno)
        self.state_time = 0
        self._notify_state_enter(self.current_state_no)

    def _notify_state_enter(self, stateno):
        try:
            self.adapter.on_state_enter(stateno)
        except Exception:
            pass

    # --------- Pausas ---------------------------------------------------------
    def _apply_pause(self, frames, superpause=False, darken=False, p2defmul=None):
        frames = int(max(0, frames))
        if superpause:
            self.superpause_ticks = frames
            try:
                self.adapter.on_superpause(frames, darken=bool(darken), p2defmul=p2defmul)
            except Exception:
                pass
        else:
            self.pause_ticks = frames
            try:
                self.adapter.on_pause(frames)
            except Exception:
                pass

    # --------- Evaluación de triggers (AST) ----------------------------------
    def _eval_trigger_expr(self, node):
        """Evalúa una expresión del AST usando el runtime/evaluator."""
        try:
            return self.rt.eval_expr(node)
        except Exception:
            return 0

    def _should_run_ctrl(self, raw_ctrl):
        """
        Respeta TriggerAll + trigger1..N si están en el AST del controller.
        Si honor_triggerall=False, ejecuta siempre.

        Robusto/compatible:
        - Acepta triggerall como nodo o como par ('triggerall', nodo).
        - Acepta triggers como lista de nodos o como lista de pares (clave, nodo).
        - Si algo falla al evaluar, considera False para no romper el frame.
        """
        if not self.honor_triggerall:
            return True

        trigall_ok = True
        triggers_ok = True

        # --- TriggerAll
        trigall_node = getattr(raw_ctrl, "triggerall", None)
        # Compat: si vino como ('triggerall', nodo), usa el nodo
        if isinstance(trigall_node, tuple) and len(trigall_node) == 2:
            trigall_node = trigall_node[1]
        if trigall_node is not None:
            try:
                trigall_ok = bool(self._eval_trigger_expr(trigall_node))
            except Exception:
                trigall_ok = False

        # --- trigger1..N  (OR)
        trig_nodes = getattr(raw_ctrl, "triggers", None)
        if trig_nodes:
            # Compat: si vienen como pares (clave, nodo), quita la clave
            try:
                if (isinstance(trig_nodes, (list, tuple)) and
                    len(trig_nodes) > 0 and
                    isinstance(trig_nodes[0], tuple)):
                    trig_nodes = [n for (_k, n) in trig_nodes]
            except Exception:
                # Si hay un formato inesperado, invalida triggers para evitar errores
                trig_nodes = []

            try:
                triggers_ok = any(bool(self._eval_trigger_expr(n)) for n in trig_nodes)
            except Exception:
                triggers_ok = False

        return trigall_ok and triggers_ok

    # --------- Bucle por frame -----------------------------------------------
    def tick(self, dt=1.0):
        """
        Avanza un frame lógico (dt no es usado internamente; tu backend puede usarlo).
        Orden:
          - Gestiona pausas.
          - Evalúa triggers y ejecuta SCTRLs del estado actual.
          - Hook post (on_after_controllers).
          - Avanza state_time si no está pausado (o si la superpause lo permite).
        """
        if self.current_state_no is None:
            return

        # 0) Pausas (si hay superpause, bloquea usualmente la mayoría de cosas)
        if self.superpause_ticks > 0:
            self.superpause_ticks -= 1
            # En superpause, aún puedes permitir algunos SCTRLs si quieres.
            # Aquí optamos por bloquear ejecución de SCTRLs del estado mientras dure.
            self._post_frame()
            return

        # Si no hay superpause, revisa pause normal
        if self.pause_ticks > 0:
            self.pause_ticks -= 1
            # Normalmente Pause frena animación/movimiento pero puedes dejar pasar algunos SCTRLs.
            # Para simplificar, aquí bloqueamos ejecución de SCTRLs del estado.
            self._post_frame()
            return

        # 1) Ejecutar SCTRLs del estado actual
        ctrls = self.plan_by_state.get(self.current_state_no, [])
        for ctrl in ctrls:
            raw = ctrl.get("raw")
            if raw is not None and not self._should_run_ctrl(raw):
                continue  # condiciones no cumplidas

            name = (ctrl.get("name") or "").lower()
            params = ctrl.get("params") or {}

            # Ejecutar vía adaptador: ctrl_<name>
            handler = getattr(self.adapter, "ctrl_" + name, None)
            if handler is None:
                # Compat: en catálogos viejos algunos nombres tienen case raro;
                # el normalizador ya lo puso en canon, pero por si acaso:
                handler = getattr(self.adapter, "ctrl_" + name.replace(".", "_"), None)

            # SCTRLs que afectan el flujo del intérprete pueden tener atajos:
            flow_taken = False
            try:
                if name == "changestate":
                    # Cambio inmediato de estado
                    new_state = params.get("value")
                    if new_state is not None:
                        self.adapter.ctrl_changestate(params, self.ctx) if handler else self.adapter.request_change_state(int(new_state))
                        flow_taken = True
                elif name == "selfstate":
                    new_state = params.get("value")
                    if new_state is not None:
                        self.adapter.ctrl_selfstate(params, self.ctx) if handler else self.adapter.request_change_state(int(new_state))
                        flow_taken = True
                elif name == "pause":
                    frames = int(params.get("time", 0))
                    movetime = int(params.get("movetime", 0))
                    # movetime podría dejar moverse al actor; aquí no lo diferenciamos.
                    self._apply_pause(frames, superpause=False)
                    # Notifica al backend
                    if handler:
                        handler(params, self.ctx)
                elif name == "superpause":
                    frames = int(params.get("time", 0))
                    darken = int(params.get("darken", 0)) != 0
                    p2defmul = params.get("p2defmul", None)
                    self._apply_pause(frames, superpause=True, darken=darken, p2defmul=p2defmul)
                    if handler:
                        handler(params, self.ctx)
                else:
                    # SCTRL normal, llama al adaptador si existe; si no, fallback
                    if handler:
                        handler(params, self.ctx)
                    else:
                        self.adapter.ctrl_fallback(name, params, self.ctx)
            except Exception as e:
                # No rompas el loop por errores de un SCTRL
                # print(f"[Interpreter] error en {name}: {e}")
                pass

            # Si hubo cambio inmediato de estado, corta la ejecución del resto del frame
            if flow_taken:
                self.state_time = 0  # reinicia cronómetro de estado
                return

        # 2) Hook post-controladores
        self._post_frame()

        # 3) Avanza cronómetro del estado
        self.state_time += 1

    def _post_frame(self):
        try:
            self.adapter.on_after_controllers(self.ctx)
        except Exception:
            pass

    # --------- Conveniencias --------------------------------------------------
    def run_fixed(self, frames=1):
        """Avanza 'frames' lógicos (útil para tests headless)."""
        for _ in range(int(frames)):
            self.tick(dt=1.0)

    def set_position(self, x=None, y=None):
        if x is not None:
            self.ctx["pos"][0] = float(x)
        if y is not None:
            self.ctx["pos"][1] = float(y)

    def set_velocity(self, vx=None, vy=None):
        if vx is not None:
            self.ctx["vel"][0] = float(vx)
        if vy is not None:
            self.ctx["vel"][1] = float(vy)
