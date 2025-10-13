# -*- coding: utf-8 -*-
from __future__ import division
# Importar primero core (crea registro)
from sctrls_core import SCTRLS, CANON, list_sctrls, get_sctrl_spec, export_sctrls_json
# Cargar catálogos (poblan el registro con @register_sctrl)
import sctrls_catalog_win  # noqa: F401
import sctrls_catalog_1x  # noqa: F401
# Compat
from sctrls_compat import normalize_sctrl

def load_catalog():
    """Asegura que los catálogos estén importados y listos."""
    # los imports ya ejecutaron los decoradores; retornamos la API útil
    return {
        "list": list_sctrls(),
        "get": get_sctrl_spec,
        "export_json": export_sctrls_json,
        "normalize": normalize_sctrl,
        "registry": SCTRLS,
        "canon": CANON,
    }
