# -*- coding: utf-8 -*-
"""题目生成器: 操作数采样、表达式构造、约束校验、去重与难度控制。

约束来自需求 5 (不产生负数、除法结果为真分数、运算符个数不超过 3);
难度规则集中定义在文件顶部的常量里。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional, Sequence

from .expression import ALL_OPERATORS, BinaryOp, Expr, Number, format_value

#: 每道题目允许出现的最大运算符个数
MAX_OPERATORS = 3

#: 每个运算符个数档位内的最大尝试次数
_ATTEMPTS_PER_LEVEL = 80

#: 运算符个数的采样权重 (下标 0 对应 1 个运算符), 以一到两步计算为主
_OPERATOR_COUNT_WEIGHTS = (0.40, 0.40, 0.20)

#: 纯整数题的占比, 其余为纯分数题 (避免整数与分数混在同一道题里)
_INTEGER_PROBLEM_SHARE = 0.65

#: 纯分数题中出现带分数的概率 (带分数难度更高, 只占少数)
_MIXED_NUMBER_SHARE_IN_FRACTION = 0.10

#: 纯分数题的运算符个数上限 (分数的三步混合运算超出小学范围)
_MAX_OPERATORS_IN_FRACTION = 2

#: 真分数的分母取值范围 (小学常见分母, 且必须小于 r)
_SMALL_DENOMINATORS = (2, 3, 4, 5, 6, 8, 9, 10, 12)

#: 答案上限的倍数: 答案不超过 r²
_MAX_VALUE_FACTOR = 1

#: 答案的分母上限 (中间分母会相乘, 不设限会出现 1'177/280 这类"怪分数")
_MAX_DENOMINATOR = 100

#: 操作数池的适用上限: 预构造操作数池复用 ``Number`` 对象可把采样成本
#: 从 1.13 µs/次 降到 0.35 µs/次, 但池的规模是 O(r²), 范围很大时建池
#: 开销反而超过收益, 因此超出该值就退回逐次采样。
_POOL_MAX_RANGE = 200


def validate_tree(expr: Expr, max_value: Optional[Fraction] = None) -> Optional[Fraction]:
    """自底向上校验表达式: 合法则返回其值, 否则返回 ``None``。

    要求 ``e1 - e2`` 中 ``e1 >= e2`` (不产生负数)、``e1 ÷ e2`` 中 ``0 < e1 < e2``
    (结果必为真分数); ``max_value`` 给出答案上限, 超出即视为不合适的题目。
    校验与求值合并成一次遍历, 因此返回值就是答案。
    """
    if isinstance(expr, Number):
        return expr.value

    left_value = validate_tree(expr.left, max_value)
    if left_value is None:
        return None
    right_value = validate_tree(expr.right, max_value)
    if right_value is None:
        return None

    if expr.op == "+":
        value = left_value + right_value
    elif expr.op == "×":
        value = left_value * right_value
    elif expr.op == "-":
        if left_value < right_value:
            return None
        value = left_value - right_value
    else:
        # 除法: 结果必须是真分数
        if right_value == 0 or left_value <= 0 or left_value >= right_value:
            return None
        value = left_value / right_value

    if max_value is not None and value > max_value:
        return None
    return value


def has_identity_operand(expr: Expr) -> bool:
    """判断 ``×`` / ``÷`` 是否直接以字面量 1 作操作数 (``1 × 6``、``4 ÷ 1``),
    这类题目等于没有运算。"""
    if isinstance(expr, Number):
        return False
    if expr.op in ("×", "÷"):
        for child in (expr.left, expr.right):
            if isinstance(child, Number) and child.value == 1:
                return True
    return has_identity_operand(expr.left) or has_identity_operand(expr.right)


@dataclass
class Problem:
    """一道题目 (编号从 1 开始, ``answer`` 是参考答案)。"""

    index: int
    expr: Expr
    answer: Fraction

    @property
    def text(self) -> str:
        """题目文本, 如 ``"1/6 + 1/8 = "`` (等号前后均带空格, 需求 2)。"""
        return f"{self.expr.render()} = "

    @property
    def answer_text(self) -> str:
        """答案文本, 如 ``"7/24"``。"""
        return format_value(self.answer)

    def to_dict(self) -> Dict[str, object]:
        """转成可直接 JSON 序列化的字典, 供 Web 接口使用。"""
        return {
            "index": self.index,
            "text": self.text,
            "display": self.text.strip(),
            "answer": self.answer_text,
            "operator_count": self.expr.op_count(),
            "answer_type": describe_answer_type(self.answer),
        }


def describe_answer_type(value: Fraction) -> str:
    """把答案归类, 用于前端展示统计图表。"""
    if value.denominator == 1:
        return "整数"
    if value.numerator < value.denominator:
        return "真分数"
    return "带分数"


@dataclass
class ProblemSet:
    """一次运行生成的整套题目及其统计信息。"""

    problems: List[Problem]
    value_range: int
    requested: int
    attempts: int = 0
    exhausted: bool = False

    def __len__(self) -> int:
        return len(self.problems)

    def __iter__(self):
        return iter(self.problems)

    def exercise_lines(self) -> List[str]:
        return [problem.text for problem in self.problems]

    def answer_lines(self) -> List[str]:
        return [problem.answer_text for problem in self.problems]

    def summarize(self) -> Dict[str, object]:
        """统计信息: 运算符分布、答案类型分布、平均运算符个数。"""
        operator_counter: Dict[str, int] = {op: 0 for op in ALL_OPERATORS}
        answer_type_counter: Dict[str, int] = {"整数": 0, "真分数": 0, "带分数": 0}
        total_operators = 0

        for problem in self.problems:
            total_operators += problem.expr.op_count()
            _count_operators(problem.expr, operator_counter)
            answer_type_counter[describe_answer_type(problem.answer)] += 1

        count = len(self.problems)
        return {
            "count": count,
            "requested": self.requested,
            "value_range": self.value_range,
            "average_operators": round(total_operators / count, 3) if count else 0.0,
            "operator_distribution": operator_counter,
            "answer_type_distribution": answer_type_counter,
            "attempts": self.attempts,
            "exhausted": self.exhausted,
        }


def _count_operators(expr: Expr, counter: Dict[str, int]) -> None:
    if isinstance(expr, BinaryOp):
        counter[expr.op] += 1
        _count_operators(expr.left, counter)
        _count_operators(expr.right, counter)


class ExpressionGenerator:
    """按数值范围 ``r`` 采样操作数并构造合法表达式; 传入固定种子的 rng 可复现。"""

    def __init__(
        self,
        value_range: int,
        rng: Optional[random.Random] = None,
        allow_mixed_numbers: bool = True,
    ) -> None:
        if value_range < 1:
            raise ValueError("数值范围 -r 必须是不小于 1 的自然数")
        self.value_range = value_range
        self.rng = rng or random.Random()
        self.allow_mixed_numbers = allow_mixed_numbers and value_range >= 3
        # 难度控制: 数值范围足够大时, 不把 0 当作操作数, 并跳过含字面量 1 的
        # 乘除 (见 has_identity_operand), 同时限制中间结果与答案的上限。
        # r <= 2 时可用数值只有 0 / 1, 再做这类过滤就没有题目可出了, 因此自动关闭。
        self.simple_operands_only = value_range >= 3
        self.max_value = Fraction(value_range ** 2 * _MAX_VALUE_FACTOR) \
            if self.simple_operands_only else None
        #: 当前正在构造的题目题型 ('integer' / 'fraction')
        self._leaf_mode = "integer"
        # 绑定方法到实例属性, 省去热路径上的属性查找
        self._random = self.rng.random
        self._build_operand_pools()

    # -- 操作数池 ----------------------------------------------------------
    def _build_operand_pools(self) -> None:
        """在数值范围较小时预构造操作数池 (见 ``_POOL_MAX_RANGE`` 说明)。

        * 自然数池: ``r >= 3`` 时从 1 开始 (不使用 0), 否则从 0 开始;
        * 真分数池: 只放分母为小学常见分母的分数。
        """
        if self.value_range > _POOL_MAX_RANGE:
            self._natural_pool: Optional[List[Number]] = None
            self._fraction_pool: Optional[List[Number]] = None
            return

        lowest = 1 if self.simple_operands_only else 0
        self._natural_pool = [Number(value) for value in range(lowest, self.value_range)]

        # 只枚举常用分母, 并以"分数值"去重 (2/4 与 1/2 是同一个数)
        seen: Dict[Fraction, Number] = {}
        for denominator in _SMALL_DENOMINATORS:
            if denominator >= self.value_range:
                continue
            for numerator in range(1, denominator):
                value = Fraction(numerator, denominator)
                if value not in seen:
                    seen[value] = Number(value)
        self._fraction_pool = list(seen.values())

    def _pick(self, pool: List[Number]) -> Number:
        """从池中均匀取一个操作数 (一次随机调用即可定位)。"""
        return pool[int(self._random() * len(pool))]

    # -- 操作数采样 --------------------------------------------------------
    def random_natural(self) -> Number:
        """采样一个自然数, 取值范围 ``[0, r-1]`` (``r >= 3`` 时为 ``[1, r-1]``)。"""
        if self._natural_pool is not None:
            return self._pick(self._natural_pool)
        lowest = 1 if self.simple_operands_only else 0
        return Number(lowest + int(self._random() * (self.value_range - lowest)))

    def random_proper_fraction(self) -> Optional[Number]:
        """采样一个真分数 ``a/b`` (``1 <= a < b``, 分母为小于 ``r`` 的常用分母)。

        ``r <= 2`` 时不存在合法真分数, 返回 ``None``。
        分母只取 ``2, 3, 4, 5, 6, 8, 9, 10, 12``, 这样分数题的结果
        不会出现 49/96、5/234 这类远超小学范围的"怪分数"。
        """
        if self.value_range < 3:
            return None
        if self._fraction_pool is not None:
            return self._pick(self._fraction_pool)

        small = [value for value in _SMALL_DENOMINATORS if value < self.value_range]
        denominator = small[int(self._random() * len(small))]
        numerator = 1 + int(self._random() * (denominator - 1))
        return Number(Fraction(numerator, denominator))

    def random_mixed_number(self) -> Optional[Number]:
        """采样一个带分数 ``w + a/b``, 整数部分与分母都小于 ``r``。

        整数部分只取 1 或 2, 避免出现 ``7'3/5 × 6'4/9`` 这种超出小学范围的计算。
        """
        if not self.allow_mixed_numbers:
            return None
        fraction = self.random_proper_fraction()
        if fraction is None:
            return None
        whole = 1 + int(self._random() * min(2, self.value_range - 2))
        return Number(whole + fraction.value)

    # -- 题型与操作数 ------------------------------------------------------
    def choose_leaf_mode(self) -> str:
        """决定这道题属于哪种题型。

        * ``integer``  —— 全部由自然数组成 (如 ``25 + 37 - 12``);
        * ``fraction`` —— 全部由真分数 / 带分数组成 (如 ``3/4 × 2/5``)。

        按题型统一采样叶子, 是为了避免出现 "1/2 ÷ 7 + 5" 这类
        整数与分数随意混在一起的题面。``r`` 很小时只有整数可用,
        直接按整型处理。
        """
        if not self.simple_operands_only:
            return "integer"
        return "integer" if self._random() < _INTEGER_PROBLEM_SHARE else "fraction"

    def random_operand(self, mode: str = "integer") -> Number:
        """按题型采样一个操作数。"""
        if mode == "fraction":
            if self.allow_mixed_numbers and self._random() < _MIXED_NUMBER_SHARE_IN_FRACTION:
                return (self.random_mixed_number()
                        or self.random_proper_fraction()
                        or self.random_natural())
            return self.random_proper_fraction() or self.random_natural()
        return self.random_natural()

    # -- 表达式构造 --------------------------------------------------------
    def build_tree(self, operator_count: int) -> Expr:
        """随机构造一棵恰好含 ``operator_count`` 个运算符的表达式树。"""
        if operator_count <= 0:
            return self.random_operand(self._leaf_mode)
        # 根节点占用 1 个运算符, 剩余的名额随机分配给左右子树
        left_ops = int(self._random() * operator_count)
        right_ops = operator_count - 1 - left_ops
        return BinaryOp(
            ALL_OPERATORS[int(self._random() * len(ALL_OPERATORS))],
            self.build_tree(left_ops),
            self.build_tree(right_ops),
        )

    def generate_expression(self, operator_count: Optional[int] = None) -> Optional[Expr]:
        """生成一个合法表达式; 始终失败时返回 ``None``。

        先从 ``operator_count`` 档位尝试, 若长时间不成功则逐级降低运算符
        个数重试, 确保 ``-r`` 很小 (题目空间极度受限) 时仍能出题。
        """
        levels: Sequence[int]
        if operator_count is None:
            levels = tuple(range(MAX_OPERATORS, 0, -1))
        else:
            levels = tuple(range(operator_count, 0, -1))

        for level in levels:
            for _ in range(_ATTEMPTS_PER_LEVEL):
                self._leaf_mode = self.choose_leaf_mode()
                effective_level = (min(level, _MAX_OPERATORS_IN_FRACTION)
                                   if self._leaf_mode == "fraction" else level)
                candidate = self.build_tree(effective_level)
                value = validate_tree(candidate, self.max_value)
                if value is None:
                    continue
                if self.simple_operands_only:
                    if value == 0:
                        continue      # 难度控制: 答案是 0 的题目 (如 3/10 - 3/10) 没有练习价值
                    if value.denominator > _MAX_DENOMINATOR:
                        continue      # 难度控制: 答案分母过大, 不适合小学
                    if has_identity_operand(candidate):
                        continue      # 难度控制: 跳过 1 × 6、4 ÷ 1 这类无意义题目
                return candidate
        return None


class ProblemGenerator:
    """题目集生成器: 组合采样、校验与去重 (需求 3, 5, 6)。"""

    def __init__(
        self,
        value_range: int,
        rng: Optional[random.Random] = None,
        max_operators: int = MAX_OPERATORS,
        allow_mixed_numbers: bool = True,
    ) -> None:
        if not 1 <= max_operators <= MAX_OPERATORS:
            raise ValueError(f"运算符个数必须在 1~{MAX_OPERATORS} 之间")
        self.value_range = value_range
        self.rng = rng or random.Random()
        self.max_operators = max_operators
        self.expression_generator = ExpressionGenerator(
            value_range, self.rng, allow_mixed_numbers
        )

    def _choose_operator_count(self) -> int:
        """按 ``_OPERATOR_COUNT_WEIGHTS`` 采样运算符个数。

        用一次 ``random()`` 加权重判断代替 ``rng.choices()``, 后者每次多花约 4 µs。
        """
        if self.max_operators == 1:
            return 1
        roll = self.rng.random()
        cumulative = 0.0
        for count, weight in enumerate(_OPERATOR_COUNT_WEIGHTS[: self.max_operators], start=1):
            cumulative += weight
            if roll < cumulative:
                return count
        return self.max_operators

    def generate(self, count: int) -> ProblemSet:
        """生成 ``count`` 道互不重复的题目 (按 ``canonical()`` 规范形式去重)。

        若受 ``-r`` 限制凑不满 ``count`` 道, 则返回已有的题目并把 ``exhausted`` 置位。
        """
        if count < 1:
            raise ValueError("题目数量 -n 必须是不小于 1 的自然数")

        seen: set[str] = set()
        problems: List[Problem] = []
        attempts = 0
        stagnant = 0
        # 连续多少次"生成出的题目与已有题目重复/不合法"之后就认为题目空间已耗尽。
        # 这个判据比"总尝试次数上限"更准确: 在题目空间充足时几乎不会触发,
        # 在 -r 很小 (题目空间确实有限) 时又能及时终止, 避免无意义的空转。
        stagnant_limit = max(5000, min(count, 20000))

        while len(problems) < count and stagnant < stagnant_limit:
            attempts += 1
            expr = self.expression_generator.generate_expression(
                self._choose_operator_count()
            )
            if expr is None:
                stagnant += 1
                continue
            key = expr.canonical()
            if key in seen:
                stagnant += 1
                continue
            seen.add(key)
            problems.append(Problem(len(problems) + 1, expr, expr.evaluate()))
            stagnant = 0

        return ProblemSet(
            problems=problems,
            value_range=self.value_range,
            requested=count,
            attempts=attempts,
            exhausted=len(problems) < count,
        )
