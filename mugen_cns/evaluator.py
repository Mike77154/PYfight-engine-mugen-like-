# -*- coding: utf-8 -*-
from __future__ import division
# Optional: AST evaluator skeleton (Py2.7)
from .ast_nodes import Num, Var, Call, Unary, Bin

class EvalContext(object):
    def __init__(self, trigger_registry, provider=None):   # ← agrega provider
        self.triggers = trigger_registry
        self.provider = provider

def eval_expr(node, ctx):
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Var):
        # strings come as Var(\"text\") in this simple model
        s = node.name
        if s and s.startswith('"') and s.endswith('"'):
            return s[1:-1]
        # otherwise, treat as variable lookup in ctx if needed
        return 0
    if isinstance(node, Unary):
        v = eval_expr(node.rhs, ctx)
        if node.op == '-': return -v
        if node.op == '+': return +v
        if node.op == '!': return 0 if v else 1
        if node.op == '~': return (~int(v)) if v is not None else 0
        return 0
    if isinstance(node, Bin):
        a = eval_expr(node.lhs, ctx); b = eval_expr(node.rhs, ctx)
        op = node.op
        if op == '+': return a + b
        if op == '-': return a - b
        if op == '*': return a * b
        if op == '/': return a / float(b)
        if op == '%': return a % b
        if op == '**': return a ** b
        if op == '==': return 1 if a == b else 0
        if op == '!=': return 1 if a != b else 0
        if op == '>': return 1 if a > b else 0
        if op == '<': return 1 if a < b else 0
        if op == '>=': return 1 if a >= b else 0
        if op == '<=': return 1 if a <= b else 0
        if op == '&&': return 1 if (a and b) else 0
        if op == '||': return 1 if (a or b) else 0
        return 0
    if isinstance(node, Call):
        name = (node.name or "").lower()
        args = [eval_expr(x, ctx) for x in node.args]
        trig = ctx.triggers.get(name)
        if trig and trig.get("impl"):
            # ANTES:
            # return trig["impl"](*([None] + args))
            # AHORA:
            return trig["impl"](ctx.provider, *args)       # ← usa provider real
        return 0
