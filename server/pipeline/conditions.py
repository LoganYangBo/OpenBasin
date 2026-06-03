"""Safe evaluation of pipeline condition expressions.

Conditions gate whether actions fire, e.g. ``amount > 100`` or
``merchant != 'Internal Transfer'``. They run on untrusted-ish pipeline YAML, so
we DO NOT use ``eval``. Instead we parse to an AST and walk a strict allowlist of
node types — comparisons, boolean/unary ops, basic arithmetic, names, literals,
and membership (``in``). Anything else (calls, attribute access, subscripting)
raises.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


class ConditionError(Exception):
    pass


def _eval(node: ast.AST, names: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, names)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        # An unknown field evaluates to None so conditions degrade gracefully.
        return names.get(node.id)
    if isinstance(node, ast.BoolOp):
        values = [_eval(v, names) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)
    if isinstance(node, ast.UnaryOp):
        val = _eval(node.operand, names)
        if isinstance(node.op, ast.Not):
            return not val
        if isinstance(node.op, ast.USub):
            return -val
        if isinstance(node.op, ast.UAdd):
            return +val
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval(node.left, names), _eval(node.right, names))
    if isinstance(node, ast.Compare):
        left = _eval(node.left, names)
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            right = _eval(comparator, names)
            if type(op) not in _CMP_OPS:
                raise ConditionError(f"Unsupported comparison: {ast.dump(op)}")
            try:
                passed = _CMP_OPS[type(op)](left, right)
            except TypeError:
                # e.g. `amount > 100` when amount is None (field absent). Treat
                # an incomparable operand as a non-match rather than crashing.
                return False
            if not passed:
                return False
            left = right
        return True
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(e, names) for e in node.elts]
    raise ConditionError(f"Disallowed expression element: {type(node).__name__}")


def evaluate(expression: str, names: dict[str, Any]) -> bool:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ConditionError(f"Invalid condition {expression!r}: {exc}") from exc
    return bool(_eval(tree, names))


def all_pass(conditions: list[str], names: dict[str, Any]) -> bool:
    """Every condition must evaluate truthy for actions to fire."""
    return all(evaluate(c, names) for c in conditions)
