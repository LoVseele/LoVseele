# -*- coding: utf-8 -*-
"""测试套件: 覆盖需求 2~9 与难度控制的每一条约束。

    python tests/test_all.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from fractions import Fraction

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import (  # noqa: E402
    BinaryOp,
    Number,
    ProblemGenerator,
    format_value,
    grade,
    parse_expression,
    parse_value,
    read_lines,
    write_lines,
    write_problem_files,
)
from src.expression import Expr  # noqa: E402
from src.generator import validate_tree  # noqa: E402


def walk_values(expr: Expr):
    """自底向上返回 [(节点, 该节点左子值, 右子值, 节点值), ...]。"""
    records = []

    def visit(node: Expr) -> Fraction:
        if isinstance(node, Number):
            return node.value
        left = visit(node.left)
        right = visit(node.right)
        if node.op == "+":
            value = left + right
        elif node.op == "-":
            value = left - right
        elif node.op == "×":
            value = left * right
        else:
            value = left / right
        records.append((node, left, right, value))
        return value

    visit(expr)
    return records


def collect_operands(expr: Expr):
    """收集表达式中出现的**字面量操作数**。"""
    operands = []

    def visit(node: Expr) -> None:
        if isinstance(node, Number):
            operands.append(node.value)
            return
        visit(node.left)
        visit(node.right)

    visit(expr)
    return operands


def numbers_in_text(text: str):
    """从题目文本里取出**所有字面出现的数字**。

    这是检验"题目中数值的范围"最直接的方式: 需求 4 约束的是题目中出现的
    自然数、真分数分子与分母 (以及带分数的整数部分), 它们都以数字形式
    出现在题目文本里。
    """
    return [int(token) for token in re.findall(r"\d+", text)]


def all_operator_counts(expr: Expr):
    return expr.op_count()


class TestValueFormatting(unittest.TestCase):
    """需求 2 / 7: 真分数与带分数的书写格式。"""

    def test_natural_number(self):
        """自然数直接输出, 分母为 1 的分数也还原成自然数。"""
        self.assertEqual(format_value(Fraction(23)), "23")
        self.assertEqual(format_value(Fraction(4, 2)), "2")
        self.assertEqual(format_value(Fraction(0)), "0")

    def test_proper_fraction(self):
        """真分数: 五分之三写作 3/5。"""
        self.assertEqual(format_value(Fraction(3, 5)), "3/5")
        self.assertEqual(format_value(Fraction(7, 24)), "7/24")

    def test_mixed_number(self):
        """带分数: 二又八分之三写作 2'3/8。"""
        self.assertEqual(format_value(Fraction(19, 8)), "2'3/8")
        self.assertEqual(format_value(Fraction(3, 2)), "1'1/2")


class TestParser(unittest.TestCase):
    """需求 9 依赖的文本解析能力。"""

    def test_parse_precedence_and_parentheses(self):
        """乘除优先级高于加减; 括号改变结构。"""
        self.assertEqual(parse_expression("2 × (3 + 4)").evaluate(), Fraction(14))
        self.assertEqual(parse_expression("7 - 2 × 3").evaluate(), Fraction(1))
        self.assertEqual(parse_expression("8 ÷ 4 ÷ 2").evaluate(), Fraction(1))

    def test_parse_fraction_and_mixed(self):
        """题面中的真分数与带分数都能被解析。"""
        self.assertEqual(parse_expression("1/6 + 1/8 = ").evaluate(), Fraction(7, 24))
        self.assertEqual(parse_expression("2'3/8 + 1/8").evaluate(), Fraction(5, 2))

    def test_parse_value(self):
        """答案文本支持自然数、真分数、带分数。"""
        self.assertEqual(parse_value("5"), Fraction(5))
        self.assertEqual(parse_value("7/24"), Fraction(7, 24))
        self.assertEqual(parse_value("2'3/8"), Fraction(19, 8))
        self.assertEqual(parse_value(" 2' 3/8 "), Fraction(19, 8))

    def test_parse_rejects_garbage(self):
        """非法文本必须抛出 ParseError, 而不是静默给出错误结果。"""
        from src import ParseError

        with self.assertRaises(ParseError):
            parse_expression("1 + + 2")
        with self.assertRaises(ParseError):
            parse_expression("(1 + 2")
        with self.assertRaises(ParseError):
            parse_expression("1/6 $ 1/8")


class TestDuplicateRule(unittest.TestCase):
    """需求 6: 交换律等价的题目视为重复, 但不做结合律展平。"""

    def test_commutative_addition(self):
        """23 + 45 与 45 + 23 是同一道题。"""
        self.assertEqual(parse_expression("23 + 45").canonical(),
                         parse_expression("45 + 23").canonical())

    def test_commutative_multiplication(self):
        """6 × 8 与 8 × 6 是同一道题。"""
        self.assertEqual(parse_expression("6 × 8").canonical(),
                         parse_expression("8 × 6").canonical())

    def test_non_commutative_operators(self):
        """减法与除法不满足交换律, 交换左右即为不同题目。"""
        self.assertNotEqual(parse_expression("7 - 3").canonical(),
                            parse_expression("3 - 7").canonical())
        self.assertNotEqual(parse_expression("2 ÷ 3").canonical(),
                            parse_expression("3 ÷ 2").canonical())

    def test_associativity_is_not_flattened(self):
        """需求原文给出的关键反例。"""
        # 3 + (2 + 1) 与 1 + 2 + 3 重复（+ 左结合, 交换后可达）
        self.assertEqual(parse_expression("3 + (2 + 1)").canonical(),
                         parse_expression("1 + 2 + 3").canonical())
        # 但 1 + 2 + 3 与 3 + 2 + 1 不重复
        self.assertNotEqual(parse_expression("1 + 2 + 3").canonical(),
                            parse_expression("3 + 2 + 1").canonical())

    def test_mixed_commutative_inside(self):
        """嵌套场景: 3 × (2 + 4) 与 (4 + 2) × 3 是同一道题。"""
        self.assertEqual(parse_expression("3 × (2 + 4)").canonical(),
                         parse_expression("(4 + 2) × 3").canonical())


class TestGenerationConstraints(unittest.TestCase):
    """需求 3 / 4 / 5: 生成题目的取值范围与合法性约束。"""

    @classmethod
    def setUpClass(cls):
        cls.problem_set = ProblemGenerator(10).generate(500)

    def test_count(self):
        """需求 3: 请求多少道就生成多少道。"""
        self.assertEqual(len(self.problem_set), 500)

    def test_operand_range(self):
        """需求 4: 题目中出现的所有数值 (自然数、真分数分子与分母) 都小于 r。"""
        for problem in self.problem_set.problems:
            for number in numbers_in_text(problem.text):
                self.assertLess(number, 10, f"数值越界: {problem.text}")

    def test_no_negative_results(self):
        """需求 5: 任何 e1 - e2 子表达式都满足 e1 >= e2, 不产生负数。"""
        for problem in self.problem_set.problems:
            for node, left, right, value in walk_values(problem.expr):
                if node.op == "-":
                    self.assertGreaterEqual(left, right, f"出现负数: {problem.text}")
                self.assertGreaterEqual(value, 0, f"结果为负: {problem.text}")

    def test_division_result_is_proper_fraction(self):
        """需求 5: e1 ÷ e2 的结果必须是真分数 (0 < 结果 < 1)。"""
        division_seen = 0
        for problem in self.problem_set.problems:
            for node, left, right, value in walk_values(problem.expr):
                if node.op == "÷":
                    division_seen += 1
                    self.assertGreater(right, 0, f"除数为 0: {problem.text}")
                    self.assertGreater(left, 0, f"除法被除数为 0: {problem.text}")
                    self.assertLess(value, 1, f"除法结果不是真分数: {problem.text}")
                    self.assertLess(value.numerator, value.denominator)
        self.assertGreater(division_seen, 0, "样本里应当出现除法题目")

    def test_operator_count_limit(self):
        """需求 5: 每道题的运算符个数不超过 3 个。"""
        for problem in self.problem_set.problems:
            self.assertLessEqual(all_operator_counts(problem.expr), 3, problem.text)

    def test_no_duplicate_problems(self):
        """需求 6: 同一批题目两两不重复。"""
        keys = [problem.expr.canonical() for problem in self.problem_set.problems]
        self.assertEqual(len(keys), len(set(keys)), "出现了重复题目")

    def test_answer_matches_expression(self):
        """端到端一致性: 把题目文本重新解析求值, 结果应与答案一致。"""
        for problem in self.problem_set.problems:
            reparsed = parse_expression(problem.text)
            self.assertEqual(reparsed.evaluate(), problem.answer, problem.text)

    def test_rendered_text_is_parseable(self):
        """题目文本必须能被自己的解析器读回 (批改功能的前提)。"""
        for problem in self.problem_set.problems:
            self.assertTrue(problem.text.endswith(" = "))
            self.assertIsInstance(parse_expression(problem.text), Expr)


class TestDifficulty(unittest.TestCase):
    """难度控制: 让题目符合小学练习的实际水平。

    这些不是需求硬性要求的规则, 而是我们为"题目要能给小学生做"而加的约束,
    同样需要用例守着, 免得以后改代码时被悄悄破坏。
    """

    @classmethod
    def setUpClass(cls):
        cls.problem_set = ProblemGenerator(10).generate(400)
        cls.wide_set = ProblemGenerator(100).generate(400)

    def test_no_zero_operand_when_range_allows(self):
        """r >= 3 时不把 0 当操作数 (0 × 5、7 + 0 这类题没有练习价值)。"""
        for problem in self.problem_set.problems:
            for operand in collect_operands(problem.expr):
                self.assertNotEqual(operand, 0, f"出现了 0: {problem.text}")

    def test_no_identity_one_in_mul_div(self):
        """乘除不以字面量 1 作操作数 (1 × 6、4 ÷ 1 等于原数, 没意义)。"""
        for problem in self.problem_set.problems:
            for node, _left, _right, _value in walk_values(problem.expr):
                if node.op in ("×", "÷"):
                    for child in (node.left, node.right):
                        if isinstance(child, Number):
                            self.assertNotEqual(child.value, 1, f"出现 1: {problem.text}")

    def test_answer_magnitude_capped(self):
        """答案不超过 r² (避免出现远超当前学习范围的大数)。"""
        for problem in self.wide_set.problems:
            self.assertLessEqual(problem.answer, 100 * 100, problem.text)

    def test_answer_denominator_capped(self):
        """答案的分母不超过 100 (避免出现 1'177/280 这类"怪分数")。"""
        for problem in self.wide_set.problems:
            self.assertLessEqual(problem.answer.denominator, 100,
                                 f"答案分母过大: {problem.text} = {problem.answer_text}")

    def test_fraction_denominators_are_common(self):
        """真分数的分母只取小学常见分母。"""
        allowed = {2, 3, 4, 5, 6, 8, 9, 10, 12}
        for problem in self.wide_set.problems:
            for operand in collect_operands(problem.expr):
                if operand.denominator != 1:
                    self.assertIn(operand.denominator, allowed,
                                  f"分母不常见: {problem.text}")

    def test_fraction_problem_has_at_most_two_operators(self):
        """纯分数题最多两步 (分数的三步混合运算超出小学范围)。"""
        checked = 0
        for problem in self.wide_set.problems:
            operands = collect_operands(problem.expr)
            if all(operand.denominator != 1 for operand in operands):
                checked += 1
                self.assertLessEqual(problem.expr.op_count(), 2, problem.text)
        self.assertGreater(checked, 0, "样本里应当出现纯分数题")

    def test_average_operator_count_is_low(self):
        """整体以一步、两步计算为主: 平均运算符个数不超过 2。"""
        summary = self.wide_set.summarize()
        self.assertLessEqual(summary["average_operators"], 2.0,
                             f"平均运算符个数过高: {summary['average_operators']}")


class TestEdgeCases(unittest.TestCase):
    """边界参数: -r 1、-r 2 等极端取值。"""

    def test_range_one(self):
        """需求 4: -r 可以设为 1。此时只有 0 可用, 程序不应崩溃。"""
        problem_set = ProblemGenerator(1).generate(10)
        self.assertGreater(len(problem_set), 0)
        keys = [problem.expr.canonical() for problem in problem_set.problems]
        self.assertEqual(len(keys), len(set(keys)))
        for problem in problem_set.problems:
            self.assertTrue(set(numbers_in_text(problem.text)) <= {0}, problem.text)

    def test_range_two(self):
        """-r 2 时不存在合法真分数, 但 1 ÷ (1 + 1) 这类题目仍应可用。"""
        problem_set = ProblemGenerator(2).generate(20)
        self.assertEqual(len(problem_set), 20)
        for problem in problem_set.problems:
            self.assertTrue(set(numbers_in_text(problem.text)) <= {0, 1}, problem.text)

    def test_impossible_request_is_reported_not_crashed(self):
        """题目空间不足时正常返回并把 exhausted 置位, 而不是死循环。"""
        problem_set = ProblemGenerator(1).generate(100000)
        self.assertTrue(problem_set.exhausted)
        self.assertLess(len(problem_set.problems), 100000)

    def test_invalid_parameters(self):
        """非法参数必须显式报错。"""
        with self.assertRaises(ValueError):
            ProblemGenerator(0)
        with self.assertRaises(ValueError):
            ProblemGenerator(10).generate(0)


class TestFileOutput(unittest.TestCase):
    """需求 7 / 8: Exercises.txt 与 Answers.txt 的落盘格式。"""

    def test_files_format(self):
        problem_set = ProblemGenerator(10).generate(50)
        with tempfile.TemporaryDirectory() as directory:
            exercise_path, answer_path = write_problem_files(
                directory, problem_set.exercise_lines(), problem_set.answer_lines()
            )
            exercise_lines = read_lines(exercise_path)
            answer_lines = read_lines(answer_path)

        self.assertEqual(len(exercise_lines), 50)
        self.assertEqual(len(answer_lines), 50)
        for exercise_line, answer_line in zip(exercise_lines, answer_lines):
            self.assertTrue(exercise_line.endswith(" = "), exercise_line)
            self.assertEqual(parse_expression(exercise_line).evaluate(),
                             parse_value(answer_line))


class TestGrading(unittest.TestCase):
    """需求 9 (附加分): 批改与统计。"""

    def setUp(self):
        self.problem_set = ProblemGenerator(10).generate(10)
        self.exercises = self.problem_set.exercise_lines()
        self.answers = list(self.problem_set.answer_lines())

    def test_all_correct(self):
        result = grade(self.exercises, self.answers)
        self.assertEqual(result.correct_ids, list(range(1, 11)))
        self.assertEqual(result.wrong_ids, [])
        self.assertEqual(result.to_grade_text(),
                         "Correct: 10 (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)\nWrong: 0 ()")

    def test_statistics_and_ids(self):
        """需求 9 规定输出格式: Correct: 5 (1, 3, 5, 7, 9)。"""
        submitted = list(self.answers)
        for index in (1, 3, 5, 7, 9):          # 把第 2/4/6/8/10 题改错 (下标从 0 开始)
            submitted[index] = "999999"
        result = grade(self.exercises, submitted)
        self.assertEqual(result.correct_ids, [1, 3, 5, 7, 9])
        self.assertEqual(result.wrong_ids, [2, 4, 6, 8, 10])
        self.assertEqual(result.to_grade_text(),
                         "Correct: 5 (1, 3, 5, 7, 9)\nWrong: 5 (2, 4, 6, 8, 10)")

    def test_equivalent_answer_forms(self):
        """5/4 与 1'1/4 视为同一个答案 (有理数精确比较)。"""
        grade_result = grade(["1/2 + 3/4"], ["1'1/4"])
        self.assertEqual(grade_result.correct_ids, [1])
        grade_result = grade(["1/2 + 3/4"], ["5/4"])
        self.assertEqual(grade_result.correct_ids, [1])

    def test_blank_and_malformed_answers(self):
        """未作答与格式不规范的答案都应记为错误, 且给出说明。"""
        result = grade(["1/6 + 1/8", "7 - 2 × 3"], ["", "abc"])
        self.assertEqual(result.wrong_ids, [1, 2])
        self.assertEqual(result.details[0].note, "未作答")
        self.assertEqual(result.details[1].note, "答案格式不规范")

    def test_missing_answer_lines(self):
        """答案行数不足时, 缺少的题目按未作答处理。"""
        result = grade(self.exercises, self.answers[:4])
        self.assertEqual(result.correct_ids, [1, 2, 3, 4])
        self.assertEqual(result.wrong_ids, [5, 6, 7, 8, 9, 10])


class TestPerformance(unittest.TestCase):
    """需求 8: 支持一万道题目的生成。"""

    def test_generate_10000_problems(self):
        started = time.perf_counter()
        problem_set = ProblemGenerator(100).generate(10000)
        elapsed = time.perf_counter() - started

        self.assertEqual(len(problem_set), 10000)
        keys = [problem.expr.canonical() for problem in problem_set.problems]
        self.assertEqual(len(set(keys)), 10000)
        self.assertLess(elapsed, 10.0, f"生成 10000 道题目耗时 {elapsed:.2f}s, 超出预期")
        print(f"\n[性能] 生成 10000 道题目耗时 {elapsed:.3f} 秒")


class TestCommandLine(unittest.TestCase):
    """需求 4: 缺少 -r 时必须报错并给出帮助信息。"""

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "myapp.py"), *args],
            capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT,
        )

    def test_missing_range_shows_help(self):
        completed = self._run("-n", "10")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("必须指定 -r", completed.stderr)
        self.assertIn("usage:", completed.stderr)
        self.assertIn("示例:", completed.stderr)

    def test_blank_answer_line_does_not_shift_others(self):
        """答案文件中间的空行代表该题未作答, 不能让它后面的答案整体错位。

        这是实测中发现的一个 bug: 读取答案文件时把空行跳过了, 于是第 3 题
        的答案被当成第 2 题的答案判分。修复后空行必须保留下来。
        """
        exercises = ["1/4 + 1/4", "1/2 + 1/2", "3/4 + 3/4"]
        answers = ["1/2", "", "1'1/2"]
        with tempfile.TemporaryDirectory() as directory:
            write_lines(os.path.join(directory, "Exercises.txt"), exercises)
            write_lines(os.path.join(directory, "Answers.txt"), answers)
            completed = self._run(
                "-e", os.path.join(directory, "Exercises.txt"),
                "-a", os.path.join(directory, "Answers.txt"),
                "-o", directory,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            grade_lines = read_lines(os.path.join(directory, "Grade.txt"))

        self.assertEqual(grade_lines[0], "Correct: 2 (1, 3)")
        self.assertEqual(grade_lines[1], "Wrong: 1 (2)")

    def test_generate_and_grade_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            generated = self._run("-n", "30", "-r", "10", "-o", directory, "-s", "2024")
            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertIn("已生成 30 道题目", generated.stdout)

            graded = self._run(
                "-e", os.path.join(directory, "Exercises.txt"),
                "-a", os.path.join(directory, "Answers.txt"),
                "-o", directory,
            )
            self.assertEqual(graded.returncode, 0, graded.stderr)

            grade_lines = read_lines(os.path.join(directory, "Grade.txt"))
            self.assertEqual(grade_lines[0],
                             "Correct: 30 (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, "
                             "14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, "
                             "28, 29, 30)")
            self.assertEqual(grade_lines[1], "Wrong: 0 ()")


if __name__ == "__main__":
    unittest.main(verbosity=2)
