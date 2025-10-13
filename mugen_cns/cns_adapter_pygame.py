# -*- coding: utf-8 -*-
from __future__ import division
"""
cns_adapterpygame.py
Adaptador Pygame para el CNSInterpreter (agnóstico del personaje).
Traduce SCTRLs a acciones sobre Pygame y servicios inyectados.

Requisitos (duck-typing):
- entity: objeto con al menos:
    .x, .y, .vx, .vy (floats)
    .facing (int, 1 o -1) [opcional]
    .set_anim(anim_no:int)         -> None        [opcional]
    .set_frame(index:int)          -> None        [opcional]
    .set_alpha(alpha_tuple:(int,int)) -> None     [opcional]
    .set_blend(mode:str)           -> None        [opcional]
    .draw(surface:pygame.Surface)  -> None
- layers: dict con superficies de destino, por ejemplo:
    {"bg": Surface, "main": Surface, "fx": Surface, "ui": Surface}
  (puedes pasar solo {"main": Surface} y el adaptador dibuja ahí)
- sound: servicio de audio con:
    .play(value_tuple, channel:int=0, volume:float=1.0) -> None
    .stop(channel:int=None) -> None
    .pan(channel:int, pan:int) -> None        # opcional
- camera: servicio con:
    .world_to_screen(x:float, y:float) -> (sx, sy)       # opcional
- fx_factory: fábrica de efectos/explods con:
    .spawn_explod(params:dict) -> Explod
    Explod debe tener: .update(), .draw(surface), .alive(bool), .id (opcional)
- screenbound_policy: callable opcional para limitar posición en pantalla

NOTA: El adaptador es conservador. Si alguna función no existe, hace no-op.
"""

import pygame
from pygame import Surface, Rect

try:
    # Debe existir en tu proyecto:
    from cns_interpreter import BaseAdapter
except ImportError:
    class BaseAdapter(object):
        def bind_interpreter(self, interpreter): self.interpreter = interpreter
        def on_state_enter(self, stateno): pass
        def on_state_exit(self, stateno): pass
        def on_after_controllers(self, ctx): pass
        def on_pause(self, frames): pass
        def on_superpause(self, frames, darken=False, p2defmul=None): pass
        def render_frame(self): pass
        def request_change_state(self, stateno): self.interpreter.change_state(stateno)
        def ctrl_fallback(self, name, params, ctx): pass


class CNSAdapterPygame(BaseAdapter):
    def __init__(self, entity, layers, sound=None, camera=None, fx_factory=None,
                 screenbound_policy=None):
        """
        entity: ver cabecera
        layers: dict de superficies destino (ej. {"main": display_surface})
        sound, camera, fx_factory: servicios inyectables (duck-typing)
        screenbound_policy: función(entity) -> None para limitar a pantalla
        """
        self.entity = entity
        self.layers = layers or {}
        self.main_surface = self.layers.get("main")  # Surface principal
        self.sound = sound
        self.camera = camera
        self.fx_factory = fx_factory
        self.screenbound_policy = screenbound_policy

        self._explods = []   # lista de objetos FX/Explod (si fx_factory existe)
        self._darken_overlay = 0  # 0..255 para SuperPause darken
        self._paused_frames = 0
        self._superpause_frames = 0

        # Opcional: prioridad de sprite (SprPriority)
        self._spr_priority = 0

    # --------------------- Hooks de ciclo de vida -----------------------------

    def bind_interpreter(self, interpreter):
        super(CNSAdapterPygame, self).bind_interpreter(interpreter)

    def on_state_enter(self, stateno):
        # Si el entity expone set_anim, intenta seleccionar anim = stateno (convención típica MUGEN)
        if hasattr(self.entity, "set_anim"):
            try:
                self.entity.set_anim(int(stateno))
            except Exception:
                pass

    def on_state_exit(self, stateno):
        # Puedes limpiar FX de estado si quieres:
        # self._explods = []
        pass

    def on_pause(self, frames):
        self._paused_frames = max(self._paused_frames, int(frames))

    def on_superpause(self, frames, darken=False, p2defmul=None):
        self._superpause_frames = max(self._superpause_frames, int(frames))
        # Si darken, subir overlay a 160~192 aprox y que caiga a 0 al terminar
        self._darken_overlay = 192 if darken else 0

    def on_after_controllers(self, ctx):
        # Aplicar física mínima pos += vel (si no está en pausa/superpause)
        if self._superpause_frames <= 0 and self._paused_frames <= 0:
            self.entity.x = float(getattr(self.entity, "x", 0.0)) + float(getattr(self.entity, "vx", 0.0))
            self.entity.y = float(getattr(self.entity, "y", 0.0)) + float(getattr(self.entity, "vy", 0.0))

        # ScreenBound opcional:
        if callable(self.screenbound_policy):
            try:
                self.screenbound_policy(self.entity)
            except Exception:
                pass

        # Actualiza FX (Explods) si hay fábrica:
        if self.fx_factory:
            alive_fx = []
            for fx in self._explods:
                try:
                    fx.update()
                except Exception:
                    pass
                # Conserva si .alive True o si no define alive (asumir True)
                if getattr(fx, "alive", True):
                    alive_fx.append(fx)
            self._explods = alive_fx

        # Disipa overlays de superpause
        if self._superpause_frames > 0:
            self._superpause_frames -= 1
            if self._superpause_frames <= 0:
                self._darken_overlay = 0

        if self._paused_frames > 0:
            self._paused_frames -= 1

    def render_frame(self):
        """
        Dibuja entity + FX en la capa principal (si existe). Si defines capas
        separadas (bg, fx, ui), úsalo desde tu loop principal.
        """
        if not isinstance(self.main_surface, Surface):
            return

        # Dibujo de FX “bg” si tu factory los clasifica (opcional)
        self._draw_fx(layer_key="bg")

        # Dibujo del personaje principal
        try:
            self._draw_entity(self.entity, self.main_surface)
        except Exception:
            pass

        # Dibujo de FX “fx” por encima
        self._draw_fx(layer_key="fx")

        # Overlays (darken de SuperPause)
        if self._darken_overlay > 0:
            self._fill_overlay(self.main_surface, (0, 0, 0), self._darken_overlay)

        # UI FX
        self._draw_fx(layer_key="ui")

    # --------------------- Utilidades de dibujo --------------------------------

    def _draw_entity(self, ent, surface):
        # Convertir mundo->pantalla si hay cámara
        x, y = getattr(ent, "x", 0.0), getattr(ent, "y", 0.0)
        if self.camera and hasattr(self.camera, "world_to_screen"):
            x, y = self.camera.world_to_screen(x, y)
        # Delega al propio entity
        ent.draw(surface)

    def _draw_fx(self, layer_key="fx"):
        if not self._explods:
            return
        surf = self.layers.get(layer_key, self.main_surface)
        if not isinstance(surf, Surface):
            return
        for fx in self._explods:
            try:
                fx.draw(surf)
            except Exception:
                pass

    @staticmethod
    def _fill_overlay(surface, color, alpha):
        overlay = Surface(surface.get_size(), pygame.SRCALPHA, 32)
        overlay.fill((color[0], color[1], color[2], int(max(0, min(255, alpha)))))
        surface.blit(overlay, (0, 0))

    # --------------------- Helpers de parámetros gráficos ----------------------

    @staticmethod
    def _apply_alpha_tuple_to_surface(surface, alpha_tuple):
        """
        M.U.G.E.N usa (src, dst) alpha (0..256). Pygame usa 0..255.
        Para un objetivo aproximado, aplicamos solo el src como global alpha.
        """
        if not isinstance(surface, Surface):
            return
        if not alpha_tuple:
            return
        src = max(0, min(256, int(alpha_tuple[0])))
        pygame_alpha = int(src * 255 / 256.0)
        try:
            surface.set_alpha(pygame_alpha)
        except Exception:
            pass

    # --------------------- SCTRLs: movimiento/física ---------------------------

    def ctrl_posadd(self, params, ctx):
        self.entity.x = float(getattr(self.entity, "x", 0.0)) + float(params.get("x", 0.0) or 0.0)
        self.entity.y = float(getattr(self.entity, "y", 0.0)) + float(params.get("y", 0.0) or 0.0)

    def ctrl_posset(self, params, ctx):
        if "x" in params and params["x"] is not None:
            self.entity.x = float(params["x"])
        if "y" in params and params["y"] is not None:
            self.entity.y = float(params["y"])

    def ctrl_veladd(self, params, ctx):
        self.entity.vx = float(getattr(self.entity, "vx", 0.0)) + float(params.get("x", 0.0) or 0.0)
        self.entity.vy = float(getattr(self.entity, "vy", 0.0)) + float(params.get("y", 0.0) or 0.0)

    def ctrl_velset(self, params, ctx):
        if "x" in params and params["x"] is not None:
            self.entity.vx = float(params["x"])
        if "y" in params and params["y"] is not None:
            self.entity.vy = float(params["y"])

    def ctrl_width(self, params, ctx):
        # En Pygame no hay “width” de colisión por defecto.
        # Si tu entity soporta hitbox configurable, propágalo:
        if hasattr(self.entity, "set_width_params"):
            try:
                self.entity.set_width_params(edge=params.get("edge"), player=params.get("player"))
            except Exception:
                pass

    # --------------------- SCTRLs: animación/estado ----------------------------

    def ctrl_changestate(self, params, ctx):
        new_state = params.get("value")
        if new_state is not None:
            self.request_change_state(int(new_state))

    def ctrl_selfstate(self, params, ctx):
        new_state = params.get("value")
        if new_state is not None:
            self.request_change_state(int(new_state))

    def ctrl_statetypeset(self, params, ctx):
        # Si tu entity tiene flags de statetype/movetype/physics, propágalos:
        for k in ("statetype", "movetype", "physics", "anim", "ctrl"):
            if k in params and hasattr(self.entity, f"set_{k}"):
                try:
                    getattr(self.entity, f"set_{k}")(params[k])
                except Exception:
                    pass
        # Cambio de anim opcional
        if "anim" in params and hasattr(self.entity, "set_anim"):
            try:
                self.entity.set_anim(int(params["anim"]))
            except Exception:
                pass

    # --------------------- SCTRLs: gráficos (transparencias/paletas) -----------

    def ctrl_trans(self, params, ctx):
        trans = (params.get("trans") or "none").lower()
        alpha = params.get("alpha", (256, 0))
        # Si entity sabe aplicar blend y alpha, úsalo:
        if hasattr(self.entity, "set_blend"):
            try:
                self.entity.set_blend(trans)
            except Exception:
                pass
        if hasattr(self.entity, "set_alpha"):
            try:
                self.entity.set_alpha(alpha)
            except Exception:
                pass
        # Si no, intenta usar la surface interna si la expone:
        if hasattr(self.entity, "surface"):
            self._apply_alpha_tuple_to_surface(getattr(self.entity, "surface"), alpha)

    def ctrl_palfx(self, params, ctx):
        # Recolor local. Si el entity tiene método, propágalo:
        if hasattr(self.entity, "apply_palfx"):
            try:
                self.entity.apply_palfx(params)
            except Exception:
                pass

    def ctrl_allpalfx(self, params, ctx):
        # FX global (BG/Lifebars también). Aquí solo aplicamos al entity + fx layer:
        self.ctrl_palfx(params, ctx)

    def ctrl_envcolor(self, params, ctx):
        # Overlay de color (1.x). Si entity sabe, propágalo:
        if hasattr(self.entity, "apply_envcolor"):
            try:
                self.entity.apply_envcolor(params)
            except Exception:
                pass

    def ctrl_remappal(self, params, ctx):
        # Remapeo de paleta. Si entity soporta:
        if hasattr(self.entity, "remap_palette"):
            try:
                self.entity.remap_palette(params.get("source"), params.get("dest"))
            except Exception:
                pass

    def ctrl_sprpriority(self, params, ctx):
        self._spr_priority = int(params.get("value", 0))

    def ctrl_screenbound(self, params, ctx):
        # Si quieres bloquear al personaje dentro de la pantalla.
        # Aquí delegamos a screenbound_policy si existe.
        if callable(self.screenbound_policy):
            try:
                self.screenbound_policy(self.entity)
            except Exception:
                pass

    # --------------------- SCTRLs: FX (Explod / ModifyExplod / RemoveExplod) ---

    def ctrl_explod(self, params, ctx):
        if not self.fx_factory:
            return
        try:
            fx = self.fx_factory.spawn_explod(params)
            if fx is not None:
                self._explods.append(fx)
        except Exception:
            pass

    def ctrl_modifyexplod(self, params, ctx):
        # Si tus FX tienen id, puedes encontrarlos y actualizarlos:
        if not self.fx_factory:
            return
        target_id = params.get("id")
        if target_id is None:
            return
        for fx in self._explods:
            if getattr(fx, "id", None) == target_id:
                try:
                    # define un método update_from_params en tu FX
                    if hasattr(fx, "update_from_params"):
                        fx.update_from_params(params)
                except Exception:
                    pass

    def ctrl_removeexplod(self, params, ctx):
        target_id = params.get("id", None)
        if target_id is None:
            # eliminar todos
            self._explods = []
            return
        self._explods = [fx for fx in self._explods if getattr(fx, "id", None) != target_id]

    # --------------------- SCTRLs: Sonido -------------------------------------

    def ctrl_playsnd(self, params, ctx):
        if not self.sound:
            return
        value = params.get("value")          # (group, index) típico
        channel = int(params.get("channel", 0) or 0)
        volume = float(params.get("volumescale", 1.0) or 1.0)
        try:
            self.sound.play(value, channel=channel, volume=volume)
        except Exception:
            pass

    def ctrl_stopsnd(self, params, ctx):
        if not self.sound:
            return
        channel = params.get("channel", None)
        try:
            self.sound.stop(channel=channel)
        except Exception:
            pass

    def ctrl_sndpan(self, params, ctx):
        if not self.sound:
            return
        channel = int(params.get("channel", 0) or 0)
        pan = int(params.get("pan", 0) or 0)     # -128..127 (por ejemplo)
        if hasattr(self.sound, "pan"):
            try:
                self.sound.pan(channel, pan)
            except Exception:
                pass

    # --------------------- SCTRLs: flujo/pausas/assert ------------------------

    def ctrl_pause(self, params, ctx):
        # El CNSInterpreter ya inicia la pausa; aquí opcionalmente toca audio/anim.
        pass

    def ctrl_superpause(self, params, ctx):
        # El CNSInterpreter ya maneja overlay y freeze; aquí puedes bajar música, etc.
        pass

    def ctrl_assertspecial(self, params, ctx):
        # Flags como: invisible, nobardisplay, noBG, noFG, etc.
        # Aplica las que tengas soporte (ej. invisible):
        flags = [params.get("flag"), params.get("flag2"), params.get("flag3")]
        if "invisible" in [str(f).lower() for f in flags if f]:
            # Implementación mínima: alpha cero
            if hasattr(self.entity, "set_alpha"):
                try:
                    self.entity.set_alpha((0, 256))
                except Exception:
                    pass

    # --------------------- Fallback -------------------------------------------

    def ctrl_fallback(self, name, params, ctx):
        # Puedes loguear o ignorar silenciosamente:
        # print(f"[Adapter] SCTRL no implementado: {name} {params}")
        pass
