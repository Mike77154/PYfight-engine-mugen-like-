# -*- coding: utf-8 -*-
from __future__ import division
from triggers_core import get_trigger_spec

# Aliases históricos y variantes comunes (se expanden según tu dataset)
ALIASES = {
    "animelement": "AnimElem",
    "p2stno": "P2StateNo",
    "round_state": "RoundState",
    "move_type": "MoveType",
    "state_type": "StateType",
    # agrega aquí lo que detectes en colecciones viejas
}

def resolve_trigger_name(name):
    """Resuelve alias y respeta el nombre canónico si existe."""
    if not name: 
        return None
    low = name.lower()
    if low in ALIASES:
        return ALIASES[low]
    spec = get_trigger_spec(name)
    return spec["name"] if spec else None

def normalize_trigger_call(name, args):
    """
    - Resuelve alias y 'case'
    - Ajusta aridad (rellena o recorta args de forma suave)
    - Devuelve (nombre_canónico, args_norm, spec) o (None, None, None)
    """
    canon = resolve_trigger_name(name)
    if not canon:
        return None, None, None
    spec = get_trigger_spec(canon)
    sig  = spec["args"] or []
    a = list(args or [])

    # Relleno/recorte suave de argumentos
    if len(a) < len(sig):
        a += [None] * (len(sig) - len(a))
    if len(a) > len(sig):
        a = a[:len(sig)]
    return spec["name"], a, spec
