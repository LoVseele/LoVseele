# -*- coding: utf-8 -*-
"""算术表达式的抽象语法树。

节点分 ``Number`` (叶子, 自然数 / 真分数 / 带分数) 与 ``BinaryOp`` (e1 op e2),
各自提供求值、运算符计数、规范形式 (用于去重) 和文本渲染。
"""

from __future__ import annotations

from fractions import Fraction
from typing import Union


#: 运算符优先级, 用于渲染时决定是否加括号
PRECEDENCE = {"+": 1, "-": 1, "×": 2, "÷": 2}

#: 满足交换律的运算符, 用于题目去重时对左右子树排序
COMMUTATIVE_OPERATORS = frozenset({"+", "×"})

#: 全部合法运算符
ALL_OPERATORS = ("+", "-", "×", "÷")


def format_value(value: Fraction) -> str:
    """把有理数格式化为题目要求的字符串 (真分数写作 3/5, 带分数写作 2'3/8)。

    >>> format_value(Fraction(3, 5))
    '3/5'
    >>> format_value(Fraction(19, 8))
    "2'3/8"
    >>> format_value(Fraction(4, 2))
    '2'
    """
    if value.denominator == 1:
        return str(value.numerator)

    sign = "-" if value < 0 else ""
    numerator = abs(value.numerator)
    denominator = value.denominator

    if numerator < denominator:                       # 真分数, 如 3/5
        return f"{sign}{numerator}/{denominator}"

    whole, remainder = divmod(numerator, denominator)  # 带分数, 如 2'3/8
    if remainder == 0:
        return f"{sign}{whole}"
    return f"{sign}{whole}'{remainder}/{denominator}"


class Expr:
    """表达式节点抽象基类。"""

    def evaluate(self) -> Fraction:  # pragma: no cover - 抽象接口
        raise NotImplementedError

    def op_count(self) -> int:  # pragma: no cover - 抽象接口
        raise NotImplementedError

    def canonical(self) -> str:  # pragma: no cover - 抽象接口
        raise NotImplementedError

    def render(self, parent_precedence: int = 0, is_right_child: bool = False) -> str:
        """渲染为人类可读的表达式文本 (运算符前后带空格, 需求 2)。"""
        raise NotImplementedError

    def __str__(self) -> str:  # pragma: no cover - 语法糖
        return self.render()


class Number(Expr):
    """叶子节点: 一个具体的数值 (自然数 / 真分数 / 带分数)。

    渲染结果被缓存到 ``_text``: 同一个 ``Number`` 对象在生成过程中会被反复
    渲染 (规范形式 + 题面文本), 缓存一次可省去大量重复的分数格式化。
    因为 ``Number`` 是只读节点, 缓存不会失效。
    """

    __slots__ = ("value", "_text")

    def __init__(self, value: Union[int, Fraction]) -> None:
        self.value = Fraction(value)
        self._text: str | None = None

    def evaluate(self) -> Fraction:
        return self.value

    def op_count(self) -> int:
        return 0

    def text(self) -> str:
        """返回 (并缓存) 该数值的文本形式。"""
        if self._text is None:
            self._text = format_value(self.value)
        return self._text

    def canonical(self) -> str:
        return self.text()

    def render(self, parent_precedence: int = 0, is_right_child: bool = False) -> str:
        return self.text()

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"Number({self.value})"


class BinaryOp(Expr):
    """内部节点: ``left op right``。"""

    __slots__ = ("op", "left", "right")

    def __init__(self, op: str, left: Expr, right: Expr) -> None:
        if op not in PRECEDENCE:
            raise ValueError(f"非法运算符: {op!r}")
        self.op = op
        self.left = left
        self.right = right

    def evaluate(self) -> Fraction:
        left_value = self.left.evaluate()
        right_value = self.right.evaluate()
        if self.op == "+":
            return left_value + right_value
        if self.op == "-":
            return left_value - right_value
        if self.op == "×":
            return left_value * right_value
        if right_value == 0:
            raise ZeroDivisionError(f"除数为 0: {self.render()}")
        return left_value / right_value

    def op_count(self) -> int:
        return 1 + self.left.op_count() + self.right.op_count()

    def canonical(self) -> str:
        """返回结构等价的规范字符串, 用于题目去重。

        ``+`` 与 ``×`` 交换左右子树后仍是同一道题, 因此递归排序两侧;
        ``-`` 与 ``÷`` 保持左右顺序。注意**不展平结合律**:
        ``1+2+3`` 与 ``3+(2+1)`` 规范形式相同 (判为重复), 但与 ``3+2+1`` 不同,
        因为后者的根节点子节点是 ``{3+2, 1}`` 而非 ``{1+2, 3}``。
        """
        if self.op in COMMUTATIVE_OPERATORS:
            first, second = self.left.canonical(), self.right.canonical()
            if second < first:                      # 字典序排序, 结果确定且唯一
                first, second = second, first
            return f"({first}{self.op}{second})"
        return f"({self.left.canonical()}{self.op}{self.right.canonical()})"

    def render(self, parent_precedence: int = 0, is_right_child: bool = False) -> str:
        """按运算优先级与结合性渲染, 只保留必要的括号。

        子表达式优先级低于父节点 (如 ``(1 + 2) × 3``), 或优先级相同且位于右侧
        (如 ``1 - (2 - 3)``) 时必须加括号, 其余情况省略。
        """
        precedence = PRECEDENCE[self.op]
        text = (
            f"{self.left.render(precedence, False)} {self.op} "
            f"{self.right.render(precedence, True)}"
        )
        if self._needs_parentheses(parent_precedence, is_right_child):
            return f"({text})"
        return text

    def _needs_parentheses(self, parent_precedence: int, is_right_child: bool) -> bool:
        precedence = PRECEDENCE[self.op]
        if precedence < parent_precedence:
            return True
        return is_right_child and precedence == parent_precedence

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"BinaryOp({self.op!r}, {self.left!r}, {self.right!r})"
