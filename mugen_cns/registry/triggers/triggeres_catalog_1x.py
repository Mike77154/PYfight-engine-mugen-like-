# -*- coding: utf-8 -*-
from __future__ import division
from triggers_core import register_trigger, INT, FLT, BOOL, STR, EXPR, v

# Triggers/afinaciones introducidas o consolidadas en 1.0/1.1

@register_trigger("AILevel", args=[], returns=INT, note="Nivel de AI (0..8 si aplica).", versions=v(dos=False, v10=True, v11=True))
def trig_ailevel(ctx): return getattr(ctx, "ai_level", lambda: 0)()

@register_trigger("HitShakeOver", args=[], returns=INT, note="1 si terminó el shake del hit.", versions=v(dos=False, v10=True, v11=True))
def trig_hitshakeover(ctx): return 1 if getattr(ctx, "hitshake_over", lambda: True)() else 0

@register_trigger("CanRecover", args=[], returns=INT, note="1 si puede tech/recuperarse.", versions=v(dos=False, v10=True, v11=True))
def trig_canrecover(ctx): return 1 if getattr(ctx, "can_recover", lambda: False)() else 0

@register_trigger("P2Dist", args=[STR], returns=FLT, note="Distancia a P2 ('x' o 'y').", versions=v(dos=False, v10=True, v11=True))
def trig_p2dist(ctx, axis):
    return getattr(ctx, "p2_dist", lambda _a: 0.0)(axis)

@register_trigger("IfElse", args=[EXPR, EXPR, EXPR], returns=EXPR, note="Operador ternario IfElse(c,t,f).", versions=v(dos=False, v10=True, v11=True))
def trig_ifelse(ctx, c, t, f):
    return t if (1 if c else 0) else f

@register_trigger("Ceil", args=[EXPR], returns=EXPR, note="Techo (math).", versions=v(dos=False, v10=True, v11=True))
def trig_ceil(ctx, x): 
    import math; 
    return int(math.ceil(float(x)))

@register_trigger("Floor", args=[EXPR], returns=EXPR, note="Piso (math).", versions=v(dos=False, v10=True, v11=True))
def trig_floor(ctx, x):
    import math; 
    return int(math.floor(float(x)))

@register_trigger("Clamp", args=[EXPR, EXPR, EXPR], returns=EXPR, note="Clamp(x, min, max).", versions=v(dos=False, v10=True, v11=True))
def trig_clamp(ctx, x, mn, mx):
    x = float(x); mn = float(mn); mx = float(mx)
    return mn if x < mn else (mx if x > mx else x)
