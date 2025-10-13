# -*- coding: utf-8 -*-
from __future__ import division
from triggers_core import register_trigger, INT, FLT, BOOL, STR, EXPR, v

# Nota: estas funciones esperan un 'ctx' (contexto de evaluación) que provee tu engine.
# Si aún no conectas el runtime, déjalas como stubs (return 0/""/False) y no pasa nada.

# —— Estado / animación / control ——————————————————————————
@register_trigger("Time", args=[], returns=INT, note="Ticks transcurridos en el estado.", versions=v(dos=True))
def trig_time(ctx): return getattr(ctx, "time_in_state", lambda: 0)()

@register_trigger("AnimTime", args=[], returns=INT, note="Tiempo restante de la anim actual.", versions=v(dos=True))
def trig_animtime(ctx): return getattr(ctx, "anim_time_left", lambda: 0)()

@register_trigger("Anim", args=[], returns=INT, note="Número de anim actual.", versions=v(dos=True))
def trig_anim(ctx): return getattr(ctx, "anim_no", lambda: 0)()

@register_trigger("AnimElem", args=[INT], returns=INT, note="1 si está en el elem N.", versions=v(dos=True))
def trig_animelem(ctx, n): return 1 if getattr(ctx, "is_in_anim_elem", lambda _n: False)(int(n)) else 0

@register_trigger("Ctrl", args=[], returns=INT, note="1 si el player tiene control.", versions=v(dos=True))
def trig_ctrl(ctx): return 1 if getattr(ctx, "has_control", lambda: False)() else 0

@register_trigger("Command", args=[STR], returns=INT, note="1 si el buffer coincide.", versions=v(dos=True))
def trig_command(ctx, s): return 1 if getattr(ctx, "command_active", lambda _s: False)(s) else 0

@register_trigger("StateNo", args=[], returns=INT, note="Número de estado actual.", versions=v(dos=True))
def trig_stateno(ctx): return getattr(ctx, "state_no", lambda: 0)()

@register_trigger("PrevStateNo", args=[], returns=INT, note="Estado previo.", versions=v(dos=True))
def trig_prevstateno(ctx): return getattr(ctx, "prev_state_no", lambda: 0)()

@register_trigger("MoveType", args=[], returns=STR, note="A/I/H.", versions=v(dos=True))
def trig_movetype(ctx): return getattr(ctx, "movetype", lambda: "I")()

@register_trigger("StateType", args=[], returns=STR, note="S/C/A/L.", versions=v(dos=True))
def trig_statetype(ctx): return getattr(ctx, "statetype", lambda: "S")()

# —— Vida / poder / KO ————————————————————————————————
@register_trigger("Life", args=[], returns=INT, note="Vida actual.", versions=v(dos=True))
def trig_life(ctx): return getattr(ctx, "life", lambda: 0)()

@register_trigger("Power", args=[], returns=INT, note="Power actual.", versions=v(dos=True))
def trig_power(ctx): return getattr(ctx, "power", lambda: 0)()

@register_trigger("Alive", args=[], returns=INT, note="1 si no está KO.", versions=v(dos=True))
def trig_alive(ctx): return 1 if getattr(ctx, "is_alive", lambda: True)() else 0

# —— Posición / velocidad ——————————————————————————————
@register_trigger("PosX", args=[], returns=FLT, note="Posición X local.", versions=v(dos=True))
def trig_posx(ctx): return getattr(ctx, "pos_x", lambda: 0.0)()

@register_trigger("PosY", args=[], returns=FLT, note="Posición Y local.", versions=v(dos=True))
def trig_posy(ctx): return getattr(ctx, "pos_y", lambda: 0.0)()

@register_trigger("VelX", args=[], returns=FLT, note="Velocidad X.", versions=v(dos=True))
def trig_velx(ctx): return getattr(ctx, "vel_x", lambda: 0.0)()

@register_trigger("VelY", args=[], returns=FLT, note="Velocidad Y.", versions=v(dos=True))
def trig_vely(ctx): return getattr(ctx, "vel_y", lambda: 0.0)()

# —— Sistema / round ————————————————————————————————
@register_trigger("GameTime", args=[], returns=INT, note="Ticks globales del match.", versions=v(dos=True))
def trig_gametime(ctx): return getattr(ctx, "game_time", lambda: 0)()

@register_trigger("RoundNo", args=[], returns=INT, note="Índice de round (1..N).", versions=v(dos=True))
def trig_roundno(ctx): return getattr(ctx, "round_no", lambda: 1)()

@register_trigger("RoundState", args=[], returns=INT, note="0=intro,1=fight,2=KO,3=over.", versions=v(dos=True))
def trig_roundstate(ctx): return getattr(ctx, "round_state", lambda: 0)()

# —— Relación con P2 / edges (clásicos) ——————————————————
@register_trigger("P2StateNo", args=[], returns=INT, note="Estado de P2.", versions=v(dos=True))
def trig_p2stateno(ctx): return getattr(ctx, "p2_state_no", lambda: 0)()

@register_trigger("P2MoveType", args=[], returns=STR, note="MoveType de P2.", versions=v(dos=True))
def trig_p2movetype(ctx): return getattr(ctx, "p2_movetype", lambda: "I")()

@register_trigger("FrontEdgeBodyDist", args=[], returns=FLT, note="Distancia a borde frontal.", versions=v(dos=True))
def trig_febd(ctx): return getattr(ctx, "front_edge_body_dist", lambda: 0.0)()

@register_trigger("BackEdgeBodyDist", args=[], returns=FLT, note="Distancia a borde trasero.", versions=v(dos=True))
def trig_bebd(ctx): return getattr(ctx, "back_edge_body_dist", lambda: 0.0)()

# —— Otros clásicos frecuentes ————————————————————————————
@register_trigger("NumHelper", args=[], returns=INT, note="Helpers activos propios.", versions=v(dos=True))
def trig_numhelper(ctx): return getattr(ctx, "num_helper", lambda: 0)()

@register_trigger("NumExplod", args=[], returns=INT, note="Explods activos propios.", versions=v(dos=False, win=True, v10=True, v11=True))
def trig_numexplod(ctx): return getattr(ctx, "num_explod", lambda: 0)()

@register_trigger("GetHitVar", args=[STR], returns=EXPR, note="Variable de golpe (time, damage, etc.).", versions=v(dos=True))
def trig_gethitvar(ctx, name): return getattr(ctx, "get_hit_var", lambda _n: 0)(name)
