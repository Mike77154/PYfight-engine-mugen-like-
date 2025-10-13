# -*- coding: utf-8 -*-
from __future__ import division
from sctrls_core import register_sctrl, SCtrlBase, INT, FLT, STR, BOOL, EXPR, TUP, IDT, v

# --- A (subset clave) ---
@register_sctrl("AfterImage",
    params={"time": INT, "length": INT, "palcolor": INT, "palinvertall": BOOL,
            "palbright": TUP, "palcontrast": TUP, "palpostbright": TUP,
            "paladd": TUP, "palmul": TUP, "timegap": INT, "framegap": INT,
            "trans": STR},
    note="Estela/afterimages con control de paleta/trans.",
    versions=v(dos=False))
class SCtrlAfterImage(SCtrlBase): pass

@register_sctrl("AfterImageTime", params={"time": INT, "value": INT},
    note="Ajusta duración de afterimages activos.", versions=v(dos=False))
class SCtrlAfterImageTime(SCtrlBase): pass

@register_sctrl("AssertSpecial",
    params={"flag": STR, "flag2": STR, "flag3": STR},
    note="Flags: intro,invisible,roundnotover,nobardisplay,noBG,noFG,nostandguard,nocrouchguard,noairguard,noautoturn,nojugglecheck,nokosnd,nokoslow,noshadow,globalnoshadow,nomusic,nowalk,timerfreeze,unguardable.",
    versions=v(dos=False))
class SCtrlAssertSpecial(SCtrlBase): pass

# --- C ---
@register_sctrl("ChangeAnim", params={"value": INT, "elem": INT},
    note="Cambia a anim y elem inicial.", versions=v(dos=False))
class SCtrlChangeAnim(SCtrlBase): pass

@register_sctrl("ChangeAnim2", params={"value": INT, "elem": INT},
    note="Para P2 en custom state usando AIR de P1 (throws).", versions=v(dos=False))
class SCtrlChangeAnim2(SCtrlBase): pass

@register_sctrl("ChangeState", params={"value": INT, "ctrl": INT},
    note="Cambia a otro estado; ctrl opcional.", versions=v(dos=True))
class SCtrlChangeState(SCtrlBase): pass

@register_sctrl("CtrlSet", params={"value": INT}, note="Da o quita ctrl.", versions=v(dos=True))
class SCtrlCtrlSet(SCtrlBase): pass

# --- D/E ---
@register_sctrl("DefenceMulSet", params={"value": FLT},
    note="Multiplica daño recibido.", versions=v(dos=False))
class SCtrlDefenceMulSet(SCtrlBase): pass

@register_sctrl("DestroySelf", params={}, note="Destruye al actor/helper.",
    versions=v(dos=True))
class SCtrlDestroySelf(SCtrlBase): pass

@register_sctrl("EnvShake",
    params={"time": INT, "freq": INT, "ampl": INT, "phase": INT},
    note="Sacude cámara.", versions=v(dos=True))
class SCtrlEnvShake(SCtrlBase): pass

@register_sctrl("Explod",
    params={"anim": INT, "id": INT, "pos": TUP, "postype": STR, "bindtime": INT, "vel": TUP, "accel": TUP,
            "removetime": INT, "sprpriority": INT, "ownpal": BOOL, "removeongethit": BOOL, "supermove": INT,
            "pausemovetime": INT, "scale": TUP, "facing": INT, "vfacing": INT, "alpha": TUP, "trans": STR},
    note="Spawnea efecto gráfico.", versions=v(dos=True))
class SCtrlExplod(SCtrlBase): pass

@register_sctrl("ExplodBindTime", params={"time": INT},
    note="Actualiza bindtime de explods.", versions=v(dos=False))
class SCtrlExplodBindTime(SCtrlBase): pass

@register_sctrl("FallEnvShake", params={"time": INT, "freq": INT, "ampl": INT, "phase": INT},
    note="Shake al caer por hitfall.", versions=v(dos=False))
class SCtrlFallEnvShake(SCtrlBase): pass

# --- H ---
@register_sctrl("Helper",
    params={"stateno": INT, "id": INT, "name": STR, "pos": TUP, "postype": STR, "facing": INT, "keyctrl": INT,
            "ownpal": BOOL, "supermove": INT, "pausemovetime": INT, "size": TUP},
    note="Crea helper con su propia SM.", versions=v(dos=True))
class SCtrlHelper(SCtrlBase): pass

@register_sctrl("HitBy", params={"value": STR, "time": INT},
    note="Permite tipos de golpe; combina con NotHitBy.", versions=v(dos=True))
class SCtrlHitBy(SCtrlBase): pass

@register_sctrl("HitDef",
    params={"attr": STR, "damage": TUP, "animtype": STR, "guardflag": STR, "hitflag": STR, "priority": TUP,
            "pausetime": TUP, "sparkno": INT, "guard.sparkno": INT, "sparkxy": TUP, "hitsound": TUP,
            "guardsound": TUP, "ground.type": STR, "ground.hittime": INT, "ground.velocity": TUP,
            "air.velocity": TUP, "fall": BOOL, "getpower": TUP, "givepower": TUP, "kill": INT},
    note="Ataque con propiedades completas.", versions=v(dos=True))
class SCtrlHitDef(SCtrlBase): pass

# --- L/M ---
@register_sctrl("LifeAdd", params={"value": INT, "kill": INT, "absolute": INT},
    note="Suma vida.", versions=v(dos=True))
class SCtrlLifeAdd(SCtrlBase): pass

@register_sctrl("ModifyExplod",
    params={"id": INT, "pos": TUP, "postype": STR, "scale": TUP, "facing": INT, "vfacing": INT, "bindtime": INT,
            "accel": TUP, "sprpriority": INT, "trans": STR, "alpha": TUP},
    note="Modifica explods existentes por id.", versions=v(dos=False))
class SCtrlModifyExplod(SCtrlBase): pass

# --- N/P ---
@register_sctrl("NotHitBy", params={"value": STR, "time": INT},
    note="Inmunidad a tipos de golpe.", versions=v(dos=True))
class SCtrlNotHitBy(SCtrlBase): pass

@register_sctrl("Pause", params={"time": INT, "movetime": INT},
    note="Pausa global (freeze).", versions=v(dos=True))
class SCtrlPause(SCtrlBase): pass

@register_sctrl("PalFX",
    params={"time": INT, "add": TUP, "mul": TUP, "sinadd": TUP, "invertall": BOOL, "color": INT},
    note="Efecto paleta local.", versions=v(dos=True))
class SCtrlPalFX(SCtrlBase): pass

@register_sctrl("PlaySnd", params={"value": TUP, "channel": INT, "volumescale": FLT},
    note="Reproduce SND grp,idx.", versions=v(dos=True))
class SCtrlPlaySnd(SCtrlBase): pass

@register_sctrl("PosAdd", params={"x": FLT, "y": FLT}, note="Desplaza posición.",
    versions=v(dos=True))
class SCtrlPosAdd(SCtrlBase): pass

@register_sctrl("PosSet", params={"x": FLT, "y": FLT}, note="Fija posición.",
    versions=v(dos=True))
class SCtrlPosSet(SCtrlBase): pass

@register_sctrl("PowerAdd", params={"value": INT}, note="Suma power.",
    versions=v(dos=True))
class SCtrlPowerAdd(SCtrlBase): pass

@register_sctrl("Projectile",
    params={"projid": INT, "projanim": INT, "projhitanim": INT, "projremanim": INT, "projcancelanim": INT,
            "projscale": TUP, "projremove": INT, "projremovetime": INT, "velocity": TUP, "accel": TUP,
            "offset": TUP, "attr": STR, "hitflag": STR, "guardflag": STR, "damage": TUP, "pausetime": TUP},
    note="Proyectil con mini-HitDef.", versions=v(dos=True))
class SCtrlProjectile(SCtrlBase): pass

@register_sctrl("RemoveExplod", params={"id": INT}, note="Elimina explods.",
    versions=v(dos=True))
class SCtrlRemoveExplod(SCtrlBase): pass

@register_sctrl("ReversalDef",
    params={"pausetime": TUP, "reversal.attr": STR, "sparkno": INT, "hitsound": TUP, "p1stateno": INT, "p2stateno": INT},
    note="Parry/contra con custom state.", versions=v(dos=True))
class SCtrlReversalDef(SCtrlBase): pass

@register_sctrl("SelfState", params={"value": INT, "ctrl": INT},
    note="Vuelve a estado propio estándar.", versions=v(dos=True))
class SCtrlSelfState(SCtrlBase): pass

@register_sctrl("SprPriority", params={"value": INT},
    note="Prioridad de sprite.", versions=v(dos=True))
class SCtrlSprPriority(SCtrlBase): pass

@register_sctrl("StateTypeSet",
    params={"statetype": STR, "movetype": STR, "physics": STR, "anim": INT, "ctrl": INT},
    note="Cambia type/movetype/physics.", versions=v(dos=True))
class SCtrlStateTypeSet(SCtrlBase): pass

@register_sctrl("SuperPause",
    params={"time": INT, "movetime": INT, "poweradd": INT, "darken": INT, "anim": INT, "p2defmul": FLT},
    note="Pausa de super.", versions=v(dos=True))
class SCtrlSuperPause(SCtrlBase): pass

@register_sctrl("TargetBind", params={"pos": TUP, "time": INT, "id": IDT, "postype": STR},
    note="Bindea al target.", versions=v(dos=True))
class SCtrlTargetBind(SCtrlBase): pass

@register_sctrl("TargetLifeAdd", params={"value": INT, "kill": INT, "id": IDT},
    note="Modifica vida de target.", versions=v(dos=True))
class SCtrlTargetLifeAdd(SCtrlBase): pass

@register_sctrl("TargetState", params={"value": INT, "id": IDT},
    note="Envía target a estado.", versions=v(dos=True))
class SCtrlTargetState(SCtrlBase): pass

@register_sctrl("Turn", params={}, note="Voltea facing.", versions=v(dos=True))
class SCtrlTurn(SCtrlBase): pass

@register_sctrl("VarAdd", params={"var": INT, "fvar": INT, "value": EXPR},
    note="Suma var/fvar.", versions=v(dos=True))
class SCtrlVarAdd(SCtrlBase): pass

@register_sctrl("VarSet", params={"var": INT, "fvar": INT, "value": EXPR},
    note="Set var/fvar.", versions=v(dos=True))
class SCtrlVarSet(SCtrlBase): pass

@register_sctrl("VelAdd", params={"x": FLT, "y": FLT},
    note="Suma a velocidad.", versions=v(dos=True))
class SCtrlVelAdd(SCtrlBase): pass

@register_sctrl("VelSet", params={"x": FLT, "y": FLT},
    note="Fija velocidad.", versions=v(dos=True))
class SCtrlVelSet(SCtrlBase): pass

@register_sctrl("Width", params={"edge": TUP, "player": TUP},
    note="Ajusta width colisión X.", versions=v(dos=True))
class SCtrlWidth(SCtrlBase): pass
