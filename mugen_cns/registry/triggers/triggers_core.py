# -*- coding: utf-8 -*-
from __future__ import division
import json

# Registro global
TRIGGERS = {}   # nombre/alias (lower) -> spec
CANON    = {}   # nombre canónico (lower) -> spec

# Tipado básico para documentación / tooling
INT, FLT, BOOL, STR, EXPR = "int", "float", "bool", "string", "expr"

def register_trigger(name, args=None, returns="int", note="", versions=None, aliases=None):
    """
    Registra un trigger.
    name:     Nombre canónico (p. ej., 'AnimTime')
    args:     Lista de tipos (INT/FLT/BOOL/STR/EXPR) o literales
    returns:  Tipo de retorno (INT/FLT/BOOL/STR/EXPR)
    note:     Descripción breve
    versions: dict {'dos','win','2001','2002','1.0','1.1'} -> bool
    aliases:  Lista de alias aceptados
    """
    def deco(fn):
        spec = {
            "name": name,
            "args": list(args or []),
            "returns": returns,
            "impl": fn,                 # implementación (puede ser stub)
            "note": note,
            "versions": versions or {},
            "aliases": [a.lower() for a in (aliases or [])],
        }
        CANON[name.lower()] = spec
        TRIGGERS[name.lower()] = spec
        for a in (aliases or []):
            TRIGGERS[a.lower()] = spec
        return fn
    return deco

# Helpers de introspección / export
def list_triggers():
    return sorted(set(spec["name"] for spec in CANON.values()))

def get_trigger_spec(name):
    return TRIGGERS.get((name or "").lower())

def export_triggers_json(path):
    data = {}
    for key, v in CANON.items():
        data[v["name"]] = {
            "args": v["args"],
            "returns": v["returns"],
            "note": v["note"],
            "versions": v["versions"],
            "aliases": v["aliases"],
        }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)

# Helper para declarar presencia por versión
def v(dos=None, win=True, y2001=True, y2002=True, v10=True, v11=True):
    return {
        "dos": bool(dos),
        "win": bool(win),
        "2001": bool(y2001),
        "2002": bool(y2002),
        "1.0": bool(v10),
        "1.1": bool(v11),
    }

__all__ = [
    "TRIGGERS", "CANON", "register_trigger", "list_triggers",
    "get_trigger_spec", "export_triggers_json",
    "INT", "FLT", "BOOL", "STR", "EXPR", "v"
]
