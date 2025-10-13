# -*- coding: utf-8 -*-
from __future__ import division

# === Integrador de runtime para CNS ==========================================
# Depende de tu paquete base (lexer/parser/loader/evaluator) y de los loaders
# de catálogos que definimos (sctrls_loader y triggers_loader).
#
# Opcional: expression_loader (si lo tienes). Si no, el integrador sigue.
# ============================================================================

import types

# --- Core del parser/loader/evaluator (de tu paquete) ------------------------
from loader import load_cns_files            # fusiona múltiples .cns
from evaluator import EvalContext, eval_expr # eval de expresiones/triggers

# --- Catálogos de runtime (que ya armamos antes) -----------------------------
# SCTRLs
try:
    from sctrls_loader import load_catalog as load_sctrl_catalog
except ImportError:
    # Fallback: interfaz vacía para no tronar si aún no copias el archivo
    def load_sctrl_catalog():
        return {
            "list": [],
            "get": lambda name: None,
            "export_json": lambda path: None,
            "normalize": lambda name, params, backend_caps=None: (name, params, None),
            "registry": {},
            "canon": {},
        }

# Triggers
try:
    from triggers_loader import load_trigger_catalog
except ImportError:
    def load_trigger_catalog():
        return {
            "list": [],
            "get": lambda name: None,
            "export_json": lambda path: None,
            "resolve": lambda name: None,
            "normalize": lambda name, args: (None, None, None),
            "registry": {},
            "canon": {},
        }

# Expresiones (opcional): si tienes funciones/helper de expr fuera de triggers
try:
    import expression_loader
except ImportError:
    expression_loader = None


class CNSRuntime(object):
    """
    Orquesta todo:
    - Carga y fusiona CNS.
    - Carga catálogos de SCTRLs y Triggers.
    - Prepara un EvalContext con el registry de triggers.
    - Normaliza controllers por estado (alias/compat/degradaciones).
    """

    def __init__(self, backend_caps=None):
        # Capacidades del backend para degradación (p. ej., soporte de 'Trans')
        self.backend_caps = dict(backend_caps or {})

        # 1) Cargar catálogos
        self.sctrl = load_sctrl_catalog()           # {"registry","normalize",...}
        self.trig  = load_trigger_catalog()         # {"registry","normalize",...}

        # 2) Contexto de evaluación de expresiones
        self.eval_ctx = EvalContext(self.trig["registry"], provider=None)  # ← nuevo

        # 3) Expresiones auxiliares (opcional)
        #    Si tu expression_loader expone algo (p.ej. funciones extra),
        #    puedes inyectarlas en el contexto aquí.
        if expression_loader and hasattr(expression_loader, "inject_into_context"):
            expression_loader.inject_into_context(self.eval_ctx)

        # 4) AST fusionado del CNS (se setea con load_cns)
        self.ast = None




    def set_provider(self, provider):
        self.eval_ctx.provider = provider  # ← setter sencillo
    # ----------------- Carga y fusión de CNS ---------------------------------
    def load_cns(self, paths):
        """
        paths: lista de rutas .cns
        Retorna el AST fusionado (el mismo que guarda en self.ast).
        """
        if isinstance(paths, (str, unicode)) if str is not unicode else isinstance(paths, str):
            paths = [paths]
        self.ast = load_cns_files(paths)
        return self.ast

    # ----------------- Utilidades de consulta --------------------------------
    def list_triggers(self):
        return list(self.trig["list"])

    def list_sctrls(self):
        return list(self.sctrl["list"])

    def get_trigger(self, name):
        return self.trig["get"](name)

    def get_sctrl(self, name):
        # Acepta alias/case por cortesía
        spec = self.sctrl["registry"].get((name or "").lower())
        if spec:
            return spec
        return self.sctrl["get"](name)

    # ----------------- Evaluación de expresiones -----------------------------
    def eval_expr(self, expr_node):
        """
        Evalúa un nodo de expresión del AST usando el EvalContext con triggers.
        """
        return eval_expr(expr_node, self.eval_ctx)

    # ----------------- Preparación de Controllers ----------------------------
    def normalize_controller(self, ctrl):
        """
        Recibe un objeto Controller del parser (con atributos como:
          - ctype (nombre textual del controlador)
          - params (dict nombre->expr_node)
          - triggers (lista/dict según tu parser)
        Devuelve un dict listo para ejecutar/renderizar en tu engine:
          {
            "name": <nombre canon (o degradado)>,
            "params": <dict nombre->valor_evaluado>,
            "spec": <spec del sctrl normalizado o None>,
            "raw":  <el controller original>,
          }
        """
        # 1) Evaluar params (expresiones -> valores)
        evaled_params = {}
        for k, v in (getattr(ctrl, "params", {}) or {}).items():
            try:
                evaled_params[k] = self.eval_expr(v)
            except Exception:
                # Fallback seguro: deja el nodo sin evaluar si algo falla
                evaled_params[k] = v

        # 2) Normalización/compat de SCTRL (alias, defaults, degradación)
        name_in = getattr(ctrl, "ctype", "")
        nname, nparams, spec = self.sctrl["normalize"](name_in, evaled_params, self.backend_caps)

        return {
            "name": nname,
            "params": nparams,
            "spec": spec,
            "raw": ctrl,
        }

    # ----------------- Iteración de estados/controllers ----------------------
    def iter_states(self):
        """
        Itera (stateno, controllers_list) del AST fusionado.
        """
        if not self.ast:
            return
        # El loader de tu paquete suele exponer .states (dict: stateno -> [Controller,...])
        for st_no, ctrls in getattr(self.ast, "states", {}).items():
            yield st_no, ctrls

    def build_runtime_plan(self, filter_fn=None):
        """
        Construye un 'plan' de ejecución por estado:
        [
          {
            "stateno": <int>,
            "controllers": [
                {"name":..., "params":..., "spec":..., "raw":...},
                ...
            ]
          },
          ...
        ]
        filter_fn(controller) -> bool opcional para filtrar controllers
        """
        plan = []
        for st_no, ctrls in self.iter_states():
            bucket = {"stateno": st_no, "controllers": []}
            for c in (ctrls or []):
                if filter_fn and not filter_fn(c):
                    continue
                bucket["controllers"].append(self.normalize_controller(c))
            plan.append(bucket)
        # Orden sugerido por número de estado
        plan.sort(key=lambda x: x["stateno"])
        return plan

    # ----------------- Export -----------------------------------------------
    def export_trigger_doc(self, path):
        """
        Exporta documentación de triggers (si tu core lo soporta).
        """
        return self.trig["export_json"](path)

    def export_sctrl_doc(self, path):
        """
        Exporta documentación de SCTRLs (si tu core lo soporta).
        """
        return self.sctrl["export_json"](path)


# ============== Helper sencillo para uso directo =============================

def integrate_cns(cns_paths, backend_caps=None):
    """
    Atajo de una sola llamada:
      - Carga catálogos (SCTRL/Triggers [+ expresiones opcional])
      - Carga y fusiona los .CNS
      - Devuelve (runtime, plan) donde 'plan' es una lista por estado con
        controllers normalizados y parámetros ya evaluados.
    """
    rt = CNSRuntime(backend_caps=backend_caps)
    rt.load_cns(cns_paths)
    plan = rt.build_runtime_plan()
    return rt, plan


# ========================= Ejemplo de uso ====================================
if __name__ == "__main__":
    # Ejemplo mínimo (ajusta rutas a tus .cns reales)
    demo_paths = ["chars/kfm/cns/kfm.cns"]
    rt, plan = integrate_cns(demo_paths, backend_caps={
        "supports_trans": True,
        "supports_envcolor": True,
        "supports_remappal": True,
    })
    print("SCTRLs cargados:", len(rt.list_sctrls()))
    print("Triggers cargados:", len(rt.list_triggers()))
    print("Estados en plan:", len(plan))
    # Mostrar los primeros controllers normalizados del primer estado
    if plan:
        print("Primer estado:", plan[0]["stateno"])
        for item in plan[0]["controllers"][:5]:
            print("  -", item["name"], item["params"])
