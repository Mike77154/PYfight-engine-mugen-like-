# -*- coding: utf-8 -*-
from __future__ import division

class Expr(object):
    pass

class Num(Expr):
    def __init__(self, value, is_float=False):
        self.value = value
        self.is_float = is_float
    def __repr__(self):
        return "Num(%s)" % (self.value,)

class Var(Expr):
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return "Var(%s)" % (self.name,)

class Call(Expr):
    def __init__(self, name, args):
        self.name = name
        self.args = args
    def __repr__(self):
        return "Call(%s,%s)" % (self.name, self.args)

class Unary(Expr):
    def __init__(self, op, rhs):
        self.op = op
        self.rhs = rhs
    def __repr__(self):
        return "Unary(%s,%s)" % (self.op, self.rhs)

class Bin(Expr):
    def __init__(self, op, lhs, rhs):
        self.op = op
        self.lhs = lhs
        self.rhs = rhs
    def __repr__(self):
        return "Bin(%s,%s,%s)" % (self.op, self.lhs, self.rhs)

class StateDef(object):
    def __init__(self, number):
        self.number = number
        self.params = {}
    def __repr__(self):
        return "StateDef(%s,%s)" % (self.number, self.params)

class Controller(object):
    def __init__(self, state_no, index, ctype):
        self.state_no = state_no
        self.index = index
        self.ctype = ctype
        self.params = {}
        self.triggers = []
        self.triggerall = None
    def __repr__(self):
        return "Ctrl(%s,%s,%s)" % (self.state_no, self.ctype, self.params)

class PlayerCNS(object):
    def __init__(self):
        self.statedefs = {}
        self.states = {}
        self.globals = {}
    def __repr__(self):
        total_ctrls = 0
        for v in self.states.values():
            total_ctrls += len(v)
        return "PlayerCNS(states=%d, defs=%d, globals=%d)" % (total_ctrls, len(self.statedefs), len(self.globals))
