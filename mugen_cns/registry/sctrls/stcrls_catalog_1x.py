# -*- coding: utf-8 -*-
from __future__ import division
from sctrls_core import register_sctrl, SCtrlBase, INT, FLT, STR, BOOL, EXPR, TUP, IDT, v

@register_sctrl("Trans", params={"trans": STR, "alpha": TUP},
    note="Transparencia del actor (add, sub, add1, none).",
    versions=v(dos=False, v10=True, v11=True))
class SCtrlTrans(SCtrlBase): pass

@register_sctrl("EnvColor", params={"value": TUP, "time": INT, "under": BOOL},
    note="Overlay de color (1.x).",
    versions=v(dos=False, v10=True, v11=True))
class SCtrlEnvColor(SCtrlBase): pass

@register_sctrl("RemapPal", params={"source": STR, "dest": STR},
    note="Remapeo de paletas (1.x).",
    versions=v(dos=False, v10=True, v11=True))
class SCtrlRemapPal(SCtrlBase): pass

@register_sctrl("VictoryQuote", params={"value": STR},
    note="Cambia la victory quote (1.x).",
    versions=v(dos=False, v10=True, v11=True))
class SCtrlVictoryQuote(SCtrlBase): pass

@register_sctrl("AllPalFX",
    params={"time": INT, "add": TUP, "mul": TUP, "sinadd": TUP, "invertall": BOOL, "color": INT},
    note="PalFX global (BG, lifebars, chars).",
    versions=v(dos=False, v10=True, v11=True))
class SCtrlAllPalFX(SCtrlBase): pass

@register_sctrl("AngleDraw", params={"value": FLT, "scale": TUP},
    note="Dibuja rotado/escalado 1 frame.", versions=v(dos=False, v10=True, v11=True))
class SCtrlAngleDraw(SCtrlBase): pass
@register_sctrl("AngleSet", params={"value": FLT},
    note="Fija ángulo de dibujo.", versions=v(dos=False, v10=True, v11=True))
class SCtrlAngleSet(SCtrlBase): pass
@register_sctrl("AngleAdd", params={"value": FLT},
    note="Suma al ángulo.", versions=v(dos=False, v10=True, v11=True))
class SCtrlAngleAdd(SCtrlBase): pass
@register_sctrl("AngleMul", params={"value": FLT},
    note="Multiplica el ángulo.", versions=v(dos=False, v10=True, v11=True))
class SCtrlAngleMul(SCtrlBase): pass

@register_sctrl("ScreenBound", params={"value": INT, "movecamera": INT},
    note="Restringe salida de pantalla/cámara.", versions=v(dos=False, v10=True, v11=True))
class SCtrlScreenBound(SCtrlBase): pass

@register_sctrl("SndPan", params={"channel": INT, "pan": INT},
    note="Pan de audio por canal.", versions=v(dos=False, v10=True, v11=True))
class SCtrlSndPan(SCtrlBase): pass

@register_sctrl("StopSnd", params={"channel": INT},
    note="Detiene canal de sonido.", versions=v(dos=False, v10=True, v11=True))
class SCtrlStopSnd(SCtrlBase): pass
