# -*- coding: utf-8 -*-
from __future__ import division
import io, os
from .parser import Parser
from .lexer import lex

def _read_text(path):
    # explicit cp1252 fallback if utf-8 fails
    data = None
    try:
        f = io.open(path, 'r', encoding='utf-8')
        data = f.read()
        f.close()
        return data
    except Exception:
        f = io.open(path, 'r', encoding='cp1252', errors='replace')
        data = f.read()
        f.close()
        return data

def load_cns_files(paths):
    parser = None
    merged = None
    for p in paths:
        txt = _read_text(p)
        ast = Parser(lex(txt)).parse_file()
        if merged is None:
            merged = ast
        else:
            # naive merge: append states and globals; override statedefs by number
            merged.statedefs.update(ast.statedefs)
            for k, v in ast.states.items():
                merged.states.setdefault(k, []).extend(v)
            for gk, gv in ast.globals.items():
                merged.globals.setdefault(gk, {}).update(gv)
    return merged
