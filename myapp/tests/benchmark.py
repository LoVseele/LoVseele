# -*- coding: utf-8 -*-
"""性能基准与效能分析: 对比三代实现生成同一批题目的耗时, 并输出 cProfile 剖析。

    python tests/benchmark.py [--profile] [--runs 3]
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import random
import sys
import time
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import BinaryOp, Number, ProblemGenerator  # noqa: E402
from src.expression import ALL_OPERATORS, Expr  # noqa: E402
from src.generator import (  # noqa: E402
    _OPERATOR_COUNT_WEIGHTS,
    _SMALL_DENOMINATORS,
    ExpressionGenerator,
)

DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
DEFAULT_SIZES = (1000, 2000, 5000, 10000)
VALUE_RANGE = 100
REPEATS = 5

#: 每次计时至少生成的题目总数, 用于摊薄计时噪声
ITERATION_TARGET = 20000
STAGNANT_LIMIT = 20000


class LegacyExpressionGenerator(ExpressionGenerator):
    """优化前的操作数采样实现: 不建操作数池, 每个操作数都用 ``randint``
    现抽分子分母、现场构造 ``Fraction`` 与 ``Number``。

    题型的划分、难度规则与其他版本完全一致 —— 三个版本必须生成同一类题目,
    对比才有意义; 差别只在于"操作数是怎么造出来的"。
    """

    def __init__(self, value_range: int, rng: Optional[random.Random] = None,
                 allow_mixed_numbers: bool = True) -> None:
        super().__init__(value_range, rng, allow_mixed_numbers)
        # 关掉操作数池, 强制走"每次现造"的慢路径
        self._natural_pool = None
        self._fraction_pool = None
        self._small_denominators = [value for value in _SMALL_DENOMINATORS
                                    if value < value_range]

    def random_natural(self) -> Number:
        lowest = 1 if self.simple_operands_only else 0
        return Number(self.rng.randint(lowest, self.value_range - 1))

    def random_proper_fraction(self) -> Optional[Number]:
        if self.value_range < 3:
            return None
        denominator = self.rng.choice(self._small_denominators)
        numerator = self.rng.randint(1, denominator - 1)
        return Number(Fraction(numerator, denominator))

    def random_mixed_number(self) -> Optional[Number]:
        if not self.allow_mixed_numbers:
            return None
        fraction = self.random_proper_fraction()
        if fraction is None:
            return None
        whole = self.rng.randint(1, min(2, self.value_range - 2))
        return Number(whole + fraction.value)

    def build_tree(self, operator_count: int) -> Expr:
        if operator_count <= 0:
            return self.random_operand(self._leaf_mode)
        left_ops = self.rng.randint(0, operator_count - 1)
        return BinaryOp(
            self.rng.choice(ALL_OPERATORS),
            self.build_tree(left_ops),
            self.build_tree(operator_count - 1 - left_ops),
        )


class LegacyProblemGenerator(ProblemGenerator):
    """版本 2 的生成器: 使用旧采样实现, 运算符个数用 ``rng.choices`` 选取。"""

    def __init__(self, value_range: int, rng: Optional[random.Random] = None,
                 max_operators: int = 3) -> None:
        super().__init__(value_range, rng=rng, max_operators=max_operators)
        self.expression_generator = LegacyExpressionGenerator(value_range, self.rng)

    def _choose_operator_count(self) -> int:
        counts = list(range(1, self.max_operators + 1))
        weights = list(_OPERATOR_COUNT_WEIGHTS[: self.max_operators])
        return self.rng.choices(counts, weights=weights, k=1)[0]


def naive_is_valid(expr: Expr) -> bool:
    """版本 1 的校验方式: 每个节点都重新求值, 不做任何缓存。

    第一版把"校验"和"求值"写成了两个独立的递归函数, 同一棵子树因此被反复
    计算 —— 这是剖析结果里 `_randbelow` / `Fraction.__new__` 之外的主要开销。
    """
    if isinstance(expr, Number):
        return True
    if not (naive_is_valid(expr.left) and naive_is_valid(expr.right)):
        return False
    left = expr.left.evaluate()          # 父节点又把子树算了一遍
    right = expr.right.evaluate()
    if expr.op == "-":
        return left >= right
    if expr.op == "÷":
        return right != 0 and 0 < left < right
    return True


def generate_naive(count: int, value_range: int, rng: random.Random) -> List[Expr]:
    """版本 1: 反复求值的校验 + 逐次求值 + 只比较题面文本的去重。

    题目的构造与合法性/难度校验与其它版本一致, 区别在于:
        * 校验时对子树反复求值;
        * 校验通过后再求值一次 (不缓存);
        * 去重只比较题面文本, 交换律等价的题目会被漏判。
    """
    generator = LegacyExpressionGenerator(value_range, rng)
    problems: List[Expr] = []
    seen_text = set()
    stagnant = 0

    while len(problems) < count and stagnant < STAGNANT_LIMIT:
        operator_count = rng.choices((1, 2, 3), _OPERATOR_COUNT_WEIGHTS)[0]
        expr = generator.generate_expression(operator_count)
        if expr is None:
            stagnant += 1
            continue
        if not naive_is_valid(expr):       # 反复求值 (实际必然通过, 纯属浪费)
            stagnant += 1
            continue
        expr.evaluate()                    # 校验之后还要再求值一次
        text = f"{expr.render()} = "       # 只能发现文本完全相同的题目
        if text in seen_text:
            stagnant += 1
            continue
        seen_text.add(text)
        problems.append(expr)
        stagnant = 0

    return problems


def generate_v2(count: int, value_range: int, rng: random.Random) -> List[Expr]:
    """版本 2: 正确但未做采样优化 (校验即求值 + 规范形式去重)。"""
    generator = LegacyProblemGenerator(value_range, rng=rng)
    return [problem.expr for problem in generator.generate(count)]


def generate_v3(count: int, value_range: int, rng: random.Random) -> List[Expr]:
    """版本 3: 最终实现 (操作数池 + 文本缓存 + 单次随机定位)。"""
    generator = ProblemGenerator(value_range, rng=rng)
    return [problem.expr for problem in generator.generate(count)]


VARIANTS: Tuple[Tuple[str, str, object], ...] = (
    ("v1_naive", "第一版: 反复求值 + 文本去重", generate_naive),
    ("v2_correct", "第二版: 校验即求值 + 规范形式去重", generate_v2),
    ("v3_optimized", "第三版: 再加操作数池与缓存", generate_v3),
)


def count_true_duplicates(expressions) -> int:
    """用**正确的**规范形式统计真实的重复题数量 (独立于被测实现)。"""
    seen = set()
    duplicates = 0
    for expr in expressions:
        key = expr.canonical()
        if key in seen:
            duplicates += 1
        seen.add(key)
    return duplicates


def benchmark(sizes=DEFAULT_SIZES) -> Dict[str, object]:
    result: Dict[str, object] = {
        "value_range": VALUE_RANGE,
        "repeats": REPEATS,
        "sizes": list(sizes),
        "variants": {},
    }

    for key, label, function in VARIANTS:
        entry = {"label": label, "time": [], "duplicates": [], "count": [], "iterations": []}
        result["variants"][key] = entry

        for size in sizes:
            # 每次计时至少生成 ITERATION_TARGET 道题目再折算单次耗时,
            # 把单次运行抖动 (系统调度、CPU 降频) 摊薄掉, 让数字可复现
            iterations = max(1, round(ITERATION_TARGET / size))

            best_time = None
            for repeat in range(REPEATS):
                rng = random.Random(1000 + repeat)
                started = time.perf_counter()
                for _ in range(iterations):
                    function(size, VALUE_RANGE, rng)
                elapsed = (time.perf_counter() - started) / iterations
                if best_time is None or elapsed < best_time:
                    best_time = elapsed

            # 真实重复题数用固定种子单独跑一次: 它是结构性质, 与计时无关
            reference_duplicates = count_true_duplicates(
                function(size, VALUE_RANGE, random.Random(1000))
            )

            entry["time"].append(round(best_time, 4))
            entry["duplicates"].append(reference_duplicates)
            entry["count"].append(size)
            entry["iterations"].append(iterations)
            print(f"[{key}] n={size:<6} 单次耗时 {best_time:.4f}s "
                  f"(每次计时跑 {iterations} 遍)  真实重复题 {reference_duplicates} 道")
        print()

    # 汇总加速比
    ratio = [
        round(result["variants"]["v2_correct"]["time"][index]
              / result["variants"]["v3_optimized"]["time"][index], 3)
        for index in range(len(sizes))
    ]
    result["speedup_v2_to_v3"] = ratio
    print("第三版相对第二版的加速比:", ", ".join(f"{value:.2f}x" for value in ratio))
    return result


def profile_variant(count: int, variant: str) -> Dict[str, object]:
    """对指定版本做 cProfile 剖析。"""
    rng = random.Random(2024)
    if variant == "v2_correct":
        generator = LegacyProblemGenerator(VALUE_RANGE, rng=rng)
    else:
        generator = ProblemGenerator(VALUE_RANGE, rng=rng)

    profiler = cProfile.Profile()
    profiler.enable()
    generator.generate(count)
    profiler.disable()

    buffer = io.StringIO()
    stats = pstats.Stats(profiler, stream=buffer).sort_stats("tottime")
    stats.print_stats(15)
    text = buffer.getvalue()

    top = []
    for (filename, lineno, name), values in stats.stats.items():
        call_count, _recursive, total_time, cumulative_time, _callers = values
        top.append({
            "name": name,
            "location": f"{os.path.basename(filename)}:{lineno}",
            "tottime": round(total_time, 4),
            "cumtime": round(cumulative_time, 4),
            "ncalls": call_count,
        })
    top.sort(key=lambda item: item["tottime"], reverse=True)

    total_calls = int(text.split("function calls")[0].split()[0].replace(",", ""))
    return {"count": count, "variant": variant, "top_functions": top[:12],
            "total_calls": total_calls, "raw": text}


def profile_optimized(count: int = 10000) -> Dict[str, object]:
    before = profile_variant(count, "v2_correct")
    after = profile_variant(count, "v3_optimized")

    print("=" * 72)
    print(f"优化前 (v2_correct) 生成 {count} 道题目: {before['total_calls']} 次函数调用")
    print(before["raw"])
    print("=" * 72)
    print(f"优化后 (v3_optimized) 生成 {count} 道题目: {after['total_calls']} 次函数调用")
    print(after["raw"])

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "profile.txt"), "w", encoding="utf-8") as handle:
        handle.write(f"cProfile 性能剖析: 生成 {count} 道题目 (r={VALUE_RANGE})\n")
        handle.write("=" * 72 + "\n\n")
        handle.write(f"【优化前 v2_correct】函数调用总数 {before['total_calls']}\n")
        handle.write(before["raw"])
        handle.write("\n\n")
        handle.write(f"【优化后 v3_optimized】函数调用总数 {after['total_calls']}\n")
        handle.write(after["raw"])

    return {"before": before, "after": after}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="性能基准与效能分析")
    parser.add_argument("--profile", action="store_true", help="运行 cProfile 性能剖析")
    parser.add_argument("--sizes", default=",".join(str(item) for item in DEFAULT_SIZES),
                        help="测试规模, 逗号分隔")
    parser.add_argument("--runs", type=int, default=3,
                        help="整体重复轮数, 每轮取最小值后再取各轮最小值 (默认 3)")
    args = parser.parse_args(argv)

    sizes = tuple(int(item) for item in args.sizes.split(",") if item.strip())

    best = None
    for run in range(max(1, args.runs)):
        print(f"\n---------- 第 {run + 1} / {args.runs} 轮 ----------")
        current = benchmark(sizes)
        if best is None:
            best = current
        else:
            for key, entry in current["variants"].items():
                target = best["variants"][key]
                for field in ("time", "duplicates", "count", "iterations"):
                    target[field] = [min(a, b) for a, b in zip(target[field], entry[field])]
            best["speedup_v2_to_v3"] = [
                round(best["variants"]["v2_correct"]["time"][index]
                      / best["variants"]["v3_optimized"]["time"][index], 3)
                for index in range(len(sizes))
            ]

    result = best
    print("\n---------- 各轮最小值汇总 ----------")
    for key in ("v1_naive", "v2_correct", "v3_optimized"):
        print(f"{key:<14}", "  ".join(f"{value:.4f}s" for value in result["variants"][key]["time"]),
              " 重复题:", result["variants"][key]["duplicates"])
    print("第三版相对第二版的加速比:", ", ".join(f"{value:.2f}x"
                                          for value in result["speedup_v2_to_v3"]))

    if args.profile:
        result["profile"] = profile_optimized(max(sizes))

    os.makedirs(DOCS_DIR, exist_ok=True)
    output_path = os.path.join(DOCS_DIR, "benchmark.json")
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)

    print(f"\n结果已写入: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
