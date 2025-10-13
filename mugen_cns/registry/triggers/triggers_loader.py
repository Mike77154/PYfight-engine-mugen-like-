# -*- coding: utf-8 -*-
from __future__ import division
from triggers_core import TRIGGERS, CANON, list_triggers, get_trigger_spec, export_triggers_json

# Cargar catálogos para poblar el registro
import triggers_catalog_classic   # noqa: F401
import triggers_catalog_1x        # noqa: F401

# Compatibilizer
from triggers_compat import normalize_trigger_call, resolve_trigger_name

def load_trigger_catalog():
    """
    Punto de entrada para tu engine:
    - Asegura catálogos importados
    - Expone helpers de introspección/compat
    """
    return {
        "list": list_triggers(),
        "get": get_trigger_spec,
        "export_json": export_triggers_json,
        "resolve": resolve_trigger_name,
        "normalize": normalize_trigger_call,
        "registry": TRIGGERS,
        "canon": CANON,
    }
