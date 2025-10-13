# -*- coding: utf-8 -*-
from __future__ import division
from sctrls_core import get_sctrl_spec, INT, FLT, STR, BOOL, EXPR, TUP

# Aliases frecuentes/históricos (case-insensitive ya está cubierto, aquí nombres alternos)
ALIASES = {
    "changeanim2": "ChangeAnim2",
    "reversal": "ReversalDef",
    "varrandom": "VarRandom",
    "appendtoclipboard": "AppendToClipboard",
    "displaytoclipboard": "DisplayToClipboard",
    # agrega aquí si detectas rarezas en tus colecciones
}

# Defaults suaves para params (si el char no los pone)
DEFAULTS = {
    "trans": "none",
    "alpha": (256, 0),
    "ownpal": 0,
    "bindtime": 0,
    "sprpriority": 0,
}

def _apply_defaults(params):
    p = dict(params or {})
    for k, v in DEFAULTS.items():
        p.setdefault(k, v)
    return p

def _downgrade_if_needed(name, params, backend_caps):
    """
    backend_caps: dict con flags del renderer/audio/engine, p. ej.:
      {
        "supports_trans": True,
        "supports_envcolor": True,
        "supports_remappal": False
      }
    Si algo no existe en el backend, lo convertimos a equivalente visual aproximado.
    """
    n = name
    p = dict(params or {})

    # Caso: Trans/alpha no soportado -> emular con PalFX/AllPalFX o ignorar alpha
    if n.lower() == "trans" and not backend_caps.get("supports_trans", True):
        # Intento de emulación: trans add/sub -> palfx add/mul aproximado
        trans = (p.get("trans") or "none").lower()
        alpha = p.get("alpha") or (256, 0)
        # Emulación naïf: si 'add' => PalFX add leve; si 'sub' => mul bajo
        if trans in ("add", "add1"):
            n = "PalFX"
            p = {"time": 1, "add": (32, 32, 32), "mul": (256, 256, 256), "color": 256}
        elif trans == "sub":
            n = "PalFX"
            p = {"time": 1, "add": (0, 0, 0), "mul": (180, 180, 180), "color": 256}
        else:
            # none -> no-op
            n = "Null"; p = {}
        # Nota: esto es best-effort

    # Caso: EnvColor no soportado -> aproximar con PalFX
    if n.lower() == "envcolor" and not backend_caps.get("supports_envcolor", True):
        col = p.get("value", (255, 255, 255))
        time = p.get("time", 1)
        n = "PalFX"; p = {"time": time, "add": col, "mul": (256, 256, 256), "color": 256}

    # Caso: RemapPal no soportado -> degradar a ownpal=1 y continuar
    if n.lower() == "remappal" and not backend_caps.get("supports_remappal", True):
        n = "Null"; p = {}  # o podrías registrar un aviso y continuar

    return n, p

def normalize_sctrl(name, params, backend_caps=None):
    """
    - Resuelve alias y case-insensitive
    - Rellena defaults
    - Degrada controllers nuevos a equivalentes antiguos si backend no soporta
    - Devuelve (name_normalizado, params_normalizados, spec) listo para instanciar/ejecutar
    """
    backend_caps = backend_caps or {}
    # 1) alias
    canon = ALIASES.get(name.lower(), name)
    spec = get_sctrl_spec(canon)
    if not spec:
        # Si el SCTRL no existe en el catálogo, devuélvelo como Null (no truena)
        return "Null", {}, get_sctrl_spec("Null") or spec

    # 2) defaults suaves
    p = _apply_defaults(params)

    # 3) degradación por capacidades del backend
    n2, p2 = _downgrade_if_needed(spec["name"], p, backend_caps)
    spec2 = get_sctrl_spec(n2) or spec
    return n2, p2, spec2
