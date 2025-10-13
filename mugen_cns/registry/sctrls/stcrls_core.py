# -*- coding: utf-8 -*-
from __future__ import division
import json

SCTRLS = {}   # name/alias(lower) -> spec dict
CANON = {}    # canonical name(lower) -> spec dict (para no duplicar alias)

# Tipos comunes
INT, FLT, STR, BOOL, EXPR, TUP, IDT = "int","float","string","bool","expr","tuple","id"

def register_sctrl(name, params=None, note="", versions=None, aliases=None):
    """Registra un SCTRL y opcionalmente alias (compat)."""
    def deco(klass):
        spec = {
            "name": name,
            "params": params or {},
            "cls": klass,
            "note": note,
            "versions": versions or {},
            "aliases": [a.lower() for a in (aliases or [])]
        }
        CANON[name.lower()] = spec
        SCTRLS[name.lower()] = spec
        for a in (aliases or []):
            SCTRLS[a.lower()] = spec
        return klass
    return deco

class SCtrlBase(object):
    """Base mínima, sin ejecución. Guarda params y triggers."""
    def __init__(self, params, triggers):
        self.params = params or {}
        self.triggers = triggers or {}

    def validate(self):
        return True

# ==== Utils ===================================================================
def list_sctrls():
    """Lista canónica sin duplicar alias."""
    return sorted(set(spec["name"] for spec in CANON.values()))

def get_sctrl_spec(name):
    """Obtén spec por nombre o alias (case-insensitive)."""
    return SCTRLS.get(name.lower())

def export_sctrls_json(path):
    data = {}
    for key, v in CANON.items():
        data[v["name"]] = {
            "params": v["params"],
            "note": v["note"],
            "versions": v["versions"],
            "aliases": v["aliases"],
        }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)

# Helper para marcar versiones
def v(dos=None, win=True, y2001=True, y2002=True, v10=True, v11=True):
    return {
        "dos": bool(dos),
        "win": bool(win),
        "2001": bool(y2001),
        "2002": bool(y2002),
        "1.0": bool(v10),
        "1.1": bool(v11),
    }

# re-export de tipos para catálogos
__all__ = [
    "SCTRLS","CANON","register_sctrl","SCtrlBase","list_sctrls","get_sctrl_spec","export_sctrls_json",
    "INT","FLT","STR","BOOL","EXPR","TUP","IDT","v"
]
