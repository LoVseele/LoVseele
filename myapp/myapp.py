#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命令行入口。

    python myapp.py -n 10 -r 10                      生成题目
    python myapp.py -e Exercises.txt -a Answers.txt  批改答案

参数说明见 ``python myapp.py -h``。
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time

# 保证以 `python myapp.py` / `python 绝对路径/myapp.py` 两种方式运行都能导入 src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import (  # noqa: E402  (必须在 sys.path 调整之后导入)
    ANSWER_FILENAME,
    EXERCISE_FILENAME,
    GRADE_FILENAME,
    ParseError,
    ProblemGenerator,
    grade,
    read_lines,
    write_grade_file,
    write_problem_files,
)

PROGRAM_NAME = "myapp.py"

_HELP_EPILOG = """
示例:
  %(prog)s -n 10 -r 10                     生成 10 道 10 以内的题目
  %(prog)s -n 10000 -r 100                 生成 10000 道 100 以内的题目
  %(prog)s -n 10 -r 10 -m 2                每个题目最多 2 个运算符
  %(prog)s -e Exercises.txt -a Answers.txt 批改题目并生成 Grade.txt

输出文件:
  Exercises.txt  题目文件 (每行一道题)
  Answers.txt    答案文件 (与题目行号一一对应)
  Grade.txt      批改结果 (仅批改模式生成)
""" % {"prog": PROGRAM_NAME}


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="小学四则运算题目生成器 (生成题目 / 批改答案)",
        epilog=_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
    )
    parser.add_argument("-n", metavar="COUNT", type=int, default=10,
                        help="生成题目的个数, 默认为 10")
    parser.add_argument("-r", metavar="RANGE", type=int, default=None,
                        help="题目中数值的范围, 生成 RANGE 以内的题目 (不含 RANGE); 生成模式下必填")
    parser.add_argument("-m", metavar="OPERATORS", type=int, default=3, choices=(1, 2, 3),
                        help="每道题目允许的最大运算符个数, 取值 1~3, 默认 3")
    parser.add_argument("-e", metavar="EXERCISE_FILE", default=None,
                        help="题目文件路径, 与 -a 搭配进入批改模式")
    parser.add_argument("-a", metavar="ANSWER_FILE", default=None,
                        help="答案文件路径, 与 -e 搭配进入批改模式")
    parser.add_argument("-o", metavar="OUTPUT_DIR", default=".",
                        help="输出目录, 默认为当前目录")
    parser.add_argument("-s", metavar="SEED", type=int, default=None,
                        help="随机种子, 用于复现同一套题目")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s 1.0.0")
    return parser


def _usage_error(message: str) -> int:
    """打印错误信息与帮助信息, 返回退出码 2。"""
    print(f"参数错误: {message}", file=sys.stderr)
    print(file=sys.stderr)
    build_parser().print_help(sys.stderr)
    return 2


def run_generate(args: argparse.Namespace) -> int:
    """生成模式: 写 Exercises.txt 与 Answers.txt。"""
    if args.r is None:                                  # 需求 4: -r 必须给定
        return _usage_error("生成题目时必须指定 -r 参数 (题目中数值的范围)。")
    if args.r < 1:
        return _usage_error("-r 必须是不小于 1 的自然数。")
    if args.n < 1:
        return _usage_error("-n 必须是不小于 1 的自然数。")

    generator = ProblemGenerator(args.r, rng=random.Random(args.s),
                                 max_operators=args.m)
    started = time.perf_counter()
    problem_set = generator.generate(args.n)
    elapsed = time.perf_counter() - started

    output_dir = os.path.abspath(args.o)
    os.makedirs(output_dir, exist_ok=True)
    exercise_path, answer_path = write_problem_files(
        output_dir, problem_set.exercise_lines(), problem_set.answer_lines()
    )

    summary = problem_set.summarize()
    print(f"已生成 {summary['count']} 道题目  (数值范围: 小于 {args.r})")
    print(f"  平均运算符个数: {summary['average_operators']}  "
          f"(上限 {args.m})")
    print(f"  运算符分布:     " + "  ".join(
        f"{op}:{count}" for op, count in summary["operator_distribution"].items()))
    print(f"  答案类型分布:   " + "  ".join(
        f"{name}:{count}" for name, count in summary["answer_type_distribution"].items()))
    print(f"  题目文件:       {exercise_path}")
    print(f"  答案文件:       {answer_path}")
    print(f"  耗时:           {elapsed:.3f} s")

    if problem_set.exhausted:
        print(f"\n提示: 受 -r {args.r} 限制, 合法且互不重复的题目最多只能生成 "
              f"{summary['count']} 道 (少于请求的 {args.n} 道)。")
    return 0


def run_grade(args: argparse.Namespace) -> int:
    """批改模式: 读题目/答案文件, 写 Grade.txt。"""
    if args.e is None or args.a is None:
        return _usage_error("-e 与 -a 必须同时给出。")

    try:
        exercise_lines = read_lines(args.e)
        answer_lines = read_lines(args.a)
    except FileNotFoundError as error:
        print(f"文件错误: {error}", file=sys.stderr)
        return 2

    if not exercise_lines:
        print(f"文件错误: 题目文件为空 ({args.e})", file=sys.stderr)
        return 2

    try:
        result = grade(exercise_lines, answer_lines)
    except ParseError as error:
        print(f"解析错误: {error}", file=sys.stderr)
        return 2

    output_dir = os.path.abspath(args.o)
    os.makedirs(output_dir, exist_ok=True)
    grade_path = write_grade_file(output_dir, result.to_grade_text())

    print(f"批改完成: 共 {result.total} 道题目")
    print(f"  {result.to_grade_text().splitlines()[0]}")
    print(f"  {result.to_grade_text().splitlines()[1]}")
    print(f"  成绩文件: {grade_path}")
    if len(answer_lines) < len(exercise_lines):
        print(f"\n提示: 答案文件只有 {len(answer_lines)} 行, "
              f"缺少的 {len(exercise_lines) - len(answer_lines)} 道题目按未作答记为错误。")
    return 0


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    grade_mode = args.e is not None or args.a is not None
    if grade_mode:
        if args.r is not None or args.n != 10 or args.m != 3:
            return _usage_error("-e/-a 批改模式不能与 -n/-r/-m 一起使用。")
        return run_grade(args)
    return run_generate(args)


if __name__ == "__main__":
    sys.exit(main())
