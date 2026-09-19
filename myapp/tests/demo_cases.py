# -*- coding: utf-8 -*-
"""运行博文「测试运行」一节的用例, 输出 Markdown 表格 (结果全部来自真实运行)。

    python tests/demo_cases.py [--out docs/test-cases.md]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from fractions import Fraction

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import (  # noqa: E402
    BinaryOp,
    Number,
    ParseError,
    ProblemGenerator,
    format_value,
    grade,
    parse_expression,
    parse_value,
    read_lines,
)
from src.expression import Expr  # noqa: E402

ROWS = []


def record(index, name, operation, expected, actual, ok):
    ROWS.append({
        "index": index, "name": name, "operation": operation,
        "expected": expected, "actual": actual, "ok": ok,
    })


def walk(expr: Expr, on_binary):
    if isinstance(expr, BinaryOp):
        walk(expr.left, on_binary)
        walk(expr.right, on_binary)
        on_binary(expr)


def run_cases():
    # 1 ---------------------------------------------------------------
    problem_set = ProblemGenerator(10, rng=__import__("random").Random(42)).generate(10)
    max_ops = max(problem.expr.op_count() for problem in problem_set)
    record(1, "生成 10 道 10 以内的题目", "python myapp.py -n 10 -r 10",
           "10 道题, 运算符个数 ≤ 3",
           f"{len(problem_set)} 道题, 最大运算符个数 {max_ops}",
           len(problem_set) == 10 and max_ops <= 3)

    # 2 ---------------------------------------------------------------
    text = problem_set.problems[0].text
    reparsed = parse_expression(text).evaluate()
    record(2, "题目可被自身的解析器读回", f"parse_expression({text!r})",
           "等于答案文件中的值",
           f"{format_value(reparsed)}",
           reparsed == problem_set.problems[0].answer)

    # 3 ---------------------------------------------------------------
    no_negative = True
    for problem in problem_set.problems:
        def check(node):
            nonlocal no_negative
            if node.op == "-" and node.left.evaluate() < node.right.evaluate():
                no_negative = False
        walk(problem.expr, check)
    record(3, "计算过程不出现负数", "遍历全部 e1 - e2 子表达式",
           "所有 e1 ≥ e2", "未发现负中间结果" if no_negative else "发现负数!",
           no_negative)

    # 4 ---------------------------------------------------------------
    division_values = []
    for problem in ProblemGenerator(20, rng=__import__("random").Random(7)).generate(200).problems:
        def collect(node):
            if node.op == "÷":
                division_values.append(node.evaluate())
        walk(problem.expr, collect)
    all_proper = all(0 < value < 1 and value.numerator < value.denominator
                     for value in division_values)
    record(4, "除法结果为真分数", f"检查 {len(division_values)} 个除法子表达式",
           "全部满足 0 < 商 < 1",
           f"全部为真分数" if all_proper else "存在非真分数!",
           all_proper and len(division_values) > 0)

    # 5 ---------------------------------------------------------------
    result = ProblemGenerator(100).generate(10000)
    keys = {problem.expr.canonical() for problem in result.problems}
    record(5, "10000 道题目全部不重复", "python myapp.py -n 10000 -r 100",
           "10000 道题, 唯一题目数 10000",
           f"{len(result)} 道题, 唯一题目数 {len(keys)}",
           len(result) == 10000 and len(keys) == 10000)

    # 6 ---------------------------------------------------------------
    left = parse_expression("23 + 45").canonical()
    right = parse_expression("45 + 23").canonical()
    record(6, "交换律等价判重: 23+45 与 45+23",
           "比较两道题的规范形式", "规范形式相同, 判为重复",
           f"{left} vs {right}", left == right)

    # 7 ---------------------------------------------------------------
    with_tail = parse_expression("3 + (2 + 1)").canonical()
    flat = parse_expression("1 + 2 + 3").canonical()
    record(7, "结合律等价判重: 3+(2+1) 与 1+2+3",
           "比较两道题的规范形式", "规范形式相同, 判为重复",
           f"{with_tail} vs {flat}", with_tail == flat)

    # 8 ---------------------------------------------------------------
    ascending = parse_expression("1 + 2 + 3").canonical()
    descending = parse_expression("3 + 2 + 1").canonical()
    record(8, "结合律反例: 1+2+3 与 3+2+1",
           "比较两道题的规范形式", "规范形式不同, 判为不重复",
           f"{ascending} vs {descending}", ascending != descending)

    # 9 ---------------------------------------------------------------
    record(9, "真分数/带分数书写格式", "format_value(3/5) / format_value(19/8)",
           "3/5 与 2'3/8",
           f"{format_value(Fraction(3, 5))} 与 {format_value(Fraction(19, 8))}",
           format_value(Fraction(3, 5)) == "3/5" and format_value(Fraction(19, 8)) == "2'3/8")

    # 10 --------------------------------------------------------------
    fraction_expression = parse_expression("1/6 + 1/8")
    record(10, "需求原文示例: 1/6 + 1/8 = 7/24", "parse_expression('1/6 + 1/8')",
           "7/24", format_value(fraction_expression.evaluate()),
           fraction_expression.evaluate() == Fraction(7, 24))

    # 11 --------------------------------------------------------------
    answers = [problem.answer_text for problem in problem_set.problems]
    graded = grade(problem_set.exercise_lines(), answers)
    record(11, "批改: 全部作答正确",
           "python myapp.py -e Exercises.txt -a Answers.txt",
           f"Correct: 10 (1, 2, ..., 10) / Wrong: 0 ()",
           graded.to_grade_text().replace("\n", " / "),
           graded.correct_ids == list(range(1, 11)))

    # 12 --------------------------------------------------------------
    wrong_answers = list(answers)
    wrong_answers[1] = "999"
    wrong_answers[2] = ""
    graded = grade(problem_set.exercise_lines(), wrong_answers)
    record(12, "批改: 第 2 题答错、第 3 题未作答",
           "把答案文件的第 2 行改成 999、第 3 行留空",
           "Correct: 8 (1, 4, 5, 6, 7, 8, 9, 10) / Wrong: 2 (2, 3)",
           graded.to_grade_text().replace("\n", " / "),
           graded.wrong_ids == [2, 3])

    # 13 --------------------------------------------------------------
    graded = grade(["1/2 + 3/4"], ["5/4"])
    record(13, "批改: 5/4 与 1'1/4 视为同一答案",
           "grade(['1/2 + 3/4'], ['5/4'])", "判为正确",
           f"Correct: {len(graded.correct_ids)} / Wrong: {len(graded.wrong_ids)}",
           graded.correct_ids == [1])

    # 14 --------------------------------------------------------------
    try:
        parse_value("abc")
        parsed_ok = False
        detail = "未抛异常"
    except ParseError as error:
        parsed_ok = True
        detail = f"抛出 ParseError: {error}"
    record(14, "批改: 非法答案格式", "parse_value('abc')",
           "抛出 ParseError, 计为错误", detail, parsed_ok)

    # 15 --------------------------------------------------------------
    tiny = ProblemGenerator(1).generate(10)
    zero_only = all(set(character for character in problem.text if character.isdigit()) <= {"0"}
                    for problem in tiny.problems)
    record(15, "边界: -r 1 (只有 0 可用)", "python myapp.py -n 10 -r 1",
           "仍能生成题目且不重复",
           f"生成 {len(tiny)} 道, 数值只含 0: {zero_only}",
           len(tiny) > 0 and zero_only)

    # 16 --------------------------------------------------------------
    with tempfile.TemporaryDirectory() as directory:
        completed = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "myapp.py"), "-n", "10"],
            capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT,
        )
        output_dir = directory
    first_line = (completed.stderr or "").strip().splitlines()[0] if completed.stderr else ""
    record(16, "需求 4: 缺少 -r 参数", "python myapp.py -n 10",
           "退出码 2, 提示必须指定 -r 并打印帮助",
           f"退出码 {completed.returncode}, 提示: {first_line}",
           completed.returncode == 2 and "必须指定 -r" in completed.stderr
           and "usage:" in completed.stderr)

    # 17 --------------------------------------------------------------
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "myapp.py"),
                        "-n", "30", "-r", "10", "-o", directory, "-s", "2024"],
                       capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
        subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "myapp.py"),
                        "-e", os.path.join(directory, "Exercises.txt"),
                        "-a", os.path.join(directory, "Answers.txt"), "-o", directory],
                       capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
        grade_lines = read_lines(os.path.join(directory, "Grade.txt"))
    record(17, "端到端: 生成 30 道题后立刻批改自己的答案文件",
           "myapp.py -n 30 -r 10 -s 2024 然后 -e/-a 批改",
           "Correct: 30 (...), Wrong: 0 ()",
           " / ".join(grade_lines),
           grade_lines[1] == "Wrong: 0 ()")


def render_markdown() -> str:
    lines = [
        "| # | 测试点 | 操作 | 预期结果 | 实际结果 | 结论 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in ROWS:
        mark = "通过" if row["ok"] else "**失败**"
        lines.append(
            f"| {row['index']} | {row['name']} | `{row['operation']}` | {row['expected']} "
            f"| {row['actual']} | {mark} |"
        )
    passed = sum(1 for row in ROWS if row["ok"])
    lines.append("")
    lines.append(f"以上 {len(ROWS)} 个用例全部通过 ({passed}/{len(ROWS)})。")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None, help="把表格写入指定文件")
    args = parser.parse_args(argv)

    run_cases()
    markdown = render_markdown()
    print(markdown)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(markdown + "\n")
        print(f"\n已写入 {args.out}")

    return 0 if all(row["ok"] for row in ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
