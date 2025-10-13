# -*- coding: utf-8 -*-
from __future__ import division
import re

TOKEN_SPEC = [
    ('SKIP',    r'[ \t\r]+'),
    ('COMMENT', r';[^\n]*'),
    ('NL',      r'\n'),
    ('LBRACK',  r'\['),
    ('RBRACK',  r'\]'),
    ('COMMA',   r','),
    ('EQ',      r'='),
    ('LP',      r'\('),
    ('RP',      r'\)'),
    ('OP',      r'(\*\*|>=|<=|==|!=|&&|\|\||[+\-*/%<>^&|!])'),
    ('FLOAT',   r'\d+\.\d+'),
    ('INT',     r'-?\d+'),
    ('IDENT',   r'[A-Za-z_][A-Za-z0-9_.]*'),
    ('STRING',  r'"[^"\n]*"'),
]

token_re = re.compile('|'.join('(?P<%s>%s)' % p for p in TOKEN_SPEC))

class Tok(object):
    def __init__(self, typ, val, line):
        self.type = typ
        self.val = val
        self.line = line
    def __repr__(self):
        return "Tok(%s,%s)" % (self.type, self.val)

def lex(s):
    line = 1
    for m in token_re.finditer(s):
        typ = m.lastgroup; val = m.group()
        if typ == 'NL':
            line += 1
            continue
        if typ in ('SKIP','COMMENT'):
            continue
        yield Tok(typ, val, line)
