# -*- coding: utf-8 -*-
from __future__ import division
import re
from .lexer import lex
from .ast_nodes import *

class Parser(object):
    def __init__(self, tokens):
        self.toks = list(tokens)
        self.i = 0
    def peek(self, k=0):
        j = self.i + k
        if j < len(self.toks):
            return self.toks[j]
        return None
    def eat(self, typ=None):
        t = self.peek()
        if not t:
            raise SyntaxError("EOF")
        if typ and t.type != typ:
            raise SyntaxError("Esperaba %s, vi %s" % (typ, t))
        self.i += 1
        return t
    def match(self, typ):
        t = self.peek()
        if t and t.type == typ:
            self.i += 1
            return True
        return False

    def parse_file(self):
        ast = PlayerCNS()
        while self.peek():
            if self.match('LBRACK'):
                sec_name, sec_args = self.parse_section_header()
                self.eat('RBRACK')
                lname = (sec_name or '').lower()
                if lname == 'statedef':
                    sd = self.parse_statedef(sec_args)
                    ast.statedefs[sd.number] = sd
                elif lname == 'state':
                    st_no, idx = sec_args
                    ctrls = ast.states.setdefault(st_no, [])
                    ctrl = self.parse_state_block(st_no, idx)
                    ctrls.extend(ctrl)
                else:
                    params = self.parse_keyvals_until_next_section()
                    ast.globals.setdefault(sec_name, {}).update(params)
            else:
                self.i += 1
        return ast

    def parse_section_header(self):
        name_tok = self.eat('IDENT')
        name = name_tok.val
        args = []
        while True:
            t = self.peek()
            if not t or t.type in ('RBRACK','NL','LBRACK'):
                break
            if t.type == 'COMMA':
                self.eat('COMMA')
                continue
            if t.type in ('INT','IDENT'):
                if t.type == 'INT':
                    args.append(int(t.val))
                else:
                    args.append(t.val)
                self.i += 1
            else:
                break
        return name, args

    def parse_statedef(self, args):
        if not args:
            raise SyntaxError("Statedef sin número")
        number = int(args[0])
        sd = StateDef(number)
        sd.params.update(self.parse_keyvals_until_next_section())
        return sd

    # parser.py (dentro de parse_state_block)
    def parse_state_block(self, state_no, idx):
        items = self.parse_keyvals_until_next_section(raw=True)
        ctrls = []
        current = None
        trigger_pat = re.compile(r'^trigger(\d+)$', re.I)

        for k, v in items:
            lk = k.lower()
            if lk == 'type':
                if current:
                    ctrls.append(current)
                current = Controller(state_no, idx, self._atom_to_ident(v))

            elif lk == 'triggerall':
                if not current:
                    current = Controller(state_no, idx, 'Null')
                # Guarda SOLO el nodo de expresión, no par (k,v)
                current.triggerall = v

            elif trigger_pat.match(lk):
                if not current:
                    current = Controller(state_no, idx, 'Null')
                # Guarda SOLO el nodo de expresión, no par (k,v)
                current.triggers.append(v)

            else:
                if not current:
                    current = Controller(state_no, idx, 'Null')
                current.params[k] = v

        if current:
            ctrls.append(current)
        return ctrls


    def parse_keyvals_until_next_section(self, raw=False):
        out = [] if raw else {}
        while True:
            t = self.peek()
            if not t or t.type == 'LBRACK':
                break
            if t.type == 'IDENT':
                key = self.eat('IDENT').val
                if self.match('EQ'):
                    expr = self.parse_expr()
                    if raw:
                        out.append((key, expr))
                    else:
                        out[key] = expr
            else:
                self.i += 1
        return out

    # ----- Expresiones -----
    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        node = self.parse_and()
        while self._accept_op('||'):
            node = Bin('||', node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_cmp()
        while self._accept_op('&&'):
            node = Bin('&&', node, self.parse_cmp())
        return node

    def parse_cmp(self):
        node = self.parse_add()
        while self._accept_op('==','!=','>','<','>=','<='):
            op = self._last_op
            rhs = self.parse_add()
            node = Bin(op, node, rhs)
        return node

    def parse_add(self):
        node = self.parse_mul()
        while self._accept_op('+','-'):
            op = self._last_op
            rhs = self.parse_mul()
            node = Bin(op, node, rhs)
        return node

    def parse_mul(self):
        node = self.parse_pow()
        while self._accept_op('*','/','%'):
            op = self._last_op
            rhs = self.parse_pow()
            node = Bin(op, node, rhs)
        return node

    def parse_pow(self):
        node = self.parse_unary()
        if self._accept_op('**'):
            node = Bin('**', node, self.parse_pow())
        return node

    def parse_unary(self):
        t = self.peek()
        if t and t.type == 'OP' and t.val in ('+','-','!','~'):
            op = self.eat('OP').val
            return Unary(op, self.parse_unary())
        return self.parse_atom()

    def parse_atom(self):
        t = self.peek()
        if not t:
            raise SyntaxError("Expresión incompleta")
        if t.type == 'LP':
            self.eat('LP')
            node = self.parse_expr()
            self.eat('RP')
            return node
        if t.type == 'INT':
            self.i += 1
            return Num(int(t.val), False)
        if t.type == 'FLOAT':
            self.i += 1
            return Num(float(t.val), True)
        if t.type == 'STRING':
            self.i += 1
            return Var(t.val)
        if t.type == 'IDENT':
            ident = self.eat('IDENT').val
            if self.match('LP'):
                args = []
                if not self.match('RP'):
                    while True:
                        args.append(self.parse_expr())
                        if self.match('RP'):
                            break
                        self.eat('COMMA')
                return Call(ident, args)
            nxt = self.peek()
            if nxt and nxt.type == 'IDENT':
                arg = self.eat('IDENT').val
                return Call(ident, [Var(arg)])
            return Var(ident)
        raise SyntaxError("Token inesperado en átomo: %r" % (t,))

    def _accept_op(self, *ops):
        t = self.peek()
        if t and t.type == 'OP' and t.val in ops:
            self._last_op = t.val
            self.i += 1
            return True
        return False

    def _atom_to_ident(self, expr):
        if isinstance(expr, Var):
            return expr.name.strip('"')
        if isinstance(expr, Num):
            return str(expr.value)
        if isinstance(expr, Call):
            return expr.name
        return str(expr)

def parse_cns_text(text):
    return Parser(lex(text)).parse_file()
