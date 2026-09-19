# -*- coding: utf-8 -*-
"""题目与答案文本的解析。

把 ``"1/6 + 1/8 = "`` 还原成表达式树, 把 ``"2'3/8"`` 还原成有理数;
运算符兼容 ``*`` ``x`` ``/`` 等写法, 题目末尾的 ``=`` 与多余空格会被忽略。
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import List, Tuple

from .expression import BinaryOp, Expr, Number

__all__ = ["ParseError", "parse_expression", "parse_value", "tokenize"]


class ParseError(ValueError):
    """文本不符合题目规范时抛出。"""


#: 单条词法规则: 带分数 > 真分数 > 自然数; 运算符兼容常见别名
_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<mixed>\d+\s*'\s*\d+\s*/\s*\d+)      # 2'3/8
      | (?P<fraction>\d+\s*/\s*\d+)             # 3/5
      | (?P<integer>\d+)                        # 23
      | (?P<operator>[+\-−×÷*xX/])              # + - × ÷ (含别名)
      | (?P<lparen>[(（])                        # ( 或全角 (
      | (?P<rparen>[)）])                        # ) 或全角 )
    )""",
    re.VERBOSE,
)

_OPERATOR_ALIASES = {
    "+": "+",
    "-": "-",
    "−": "-",   # U+2212 MINUS SIGN, 与题面符号一致
    "×": "×",
    "*": "×",
    "x": "×",
    "X": "×",
    "÷": "÷",
    "/": "÷",
}

Token = Tuple[str, str]  # (类型, 原始文本)


def tokenize(text: str) -> List[Token]:
    """把文本切分为词法单元列表 (出现无法识别的字符时抛出 ParseError)。"""
    tokens: List[Token] = []
    position = 0
    length = len(text)

    while position < length:
        if text[position] in "= \t\r\n":      # 等号与空白只作分隔符
            position += 1
            continue

        match = _TOKEN_RE.match(text, position)
        if match is None or match.end() == position:
            raise ParseError(f"无法识别的字符: {text[position]!r} (位置 {position})")

        position = match.end()
        if match.group("operator"):
            tokens.append(("operator", _OPERATOR_ALIASES[match.group("operator")]))
        elif match.group("lparen"):
            tokens.append(("lparen", "("))
        elif match.group("rparen"):
            tokens.append(("rparen", ")"))
        else:
            raw = match.group("mixed") or match.group("fraction") or match.group("integer")
            tokens.append(("number", re.sub(r"\s+", "", raw)))

    if not tokens:
        raise ParseError("表达式为空")
    return tokens


def _value_from_token(raw: str) -> Fraction:
    """把 ``"2'3/8"`` / ``"3/5"`` / ``"23"`` 一类的词法单元转成有理数, 格式非法时抛出 ParseError。"""
    try:
        if "'" in raw:
            whole_text, fraction_text = raw.split("'", 1)
            numerator, denominator = fraction_text.split("/")
            return Fraction(int(whole_text) * int(denominator) + int(numerator),
                            int(denominator))
        if "/" in raw:
            numerator, denominator = raw.split("/")
            if int(denominator) == 0:
                raise ParseError(f"分母不能为 0: {raw!r}")
            return Fraction(int(numerator), int(denominator))
        return Fraction(int(raw))
    except (ValueError, ZeroDivisionError) as error:
        raise ParseError(f"无法解析的数值: {raw!r} ({error})") from error


class _Parser:
    """递归下降解析器。

    文法是标准的四则运算文法::

        expression -> term (('+' | '-') term)*
        term       -> factor (('×' | '÷') factor)*
        factor     -> number | '(' expression ')'
    """

    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.position = 0

    # -- 基础工具 ----------------------------------------------------------
    def _peek(self) -> Token | None:
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    def _consume(self) -> Token:
        if self.position >= len(self.tokens):
            raise ParseError("表达式在预期之外结束")
        token = self.tokens[self.position]
        self.position += 1
        return token

    # -- 各优先级 ----------------------------------------------------------
    def parse_expression(self) -> Expr:
        node = self.parse_term()
        while True:
            token = self._peek()
            if token and token[0] == "operator" and token[1] in ("+", "-"):
                self._consume()
                node = BinaryOp(token[1], node, self.parse_term())
            else:
                return node

    def parse_term(self) -> Expr:
        node = self.parse_factor()
        while True:
            token = self._peek()
            if token and token[0] == "operator" and token[1] in ("×", "÷"):
                self._consume()
                node = BinaryOp(token[1], node, self.parse_factor())
            else:
                return node

    def parse_factor(self) -> Expr:
        token = self._consume()
        if token[0] == "number":
            return Number(_value_from_token(token[1]))
        if token[0] == "lparen":
            node = self.parse_expression()
            closing = self._consume()
            if closing[0] != "rparen":
                raise ParseError("括号不匹配: 缺少右括号")
            return node
        raise ParseError(f"意外的记号: {token[1]!r}")


def parse_expression(text: str) -> Expr:
    """把题目文本解析为表达式树。

    >>> parse_expression("1/6 + 1/8 = ").evaluate()
    Fraction(7, 24)
    >>> str(parse_expression("2 × (3 + 4)"))
    '2 × (3 + 4)'
    """
    parser = _Parser(tokenize(text))
    expr = parser.parse_expression()
    if parser.position != len(parser.tokens):
        leftover = parser.tokens[parser.position][1]
        raise ParseError(f"表达式存在多余内容: {leftover!r}")
    return expr


def parse_value(text: str) -> Fraction:
    """把答案文本解析为有理数 (支持自然数、真分数、带分数)。

    >>> parse_value("7/24")
    Fraction(7, 24)
    >>> parse_value("2'3/8")
    Fraction(19, 8)
    """
    cleaned = re.sub(r"\s+", "", text or "")
    if not cleaned:
        raise ParseError("答案为空")

    negative = cleaned.startswith("-")
    if negative:
        cleaned = cleaned[1:]
    value = _value_from_token(cleaned)
    return -value if negative else value
