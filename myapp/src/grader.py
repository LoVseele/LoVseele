# -*- coding: utf-8 -*-
"""批改: 逐题计算标准答案并与提交答案比对, 输出 Grade.txt 的内容。

比对使用 ``Fraction`` 精确相等, 因此 ``5/4`` 与 ``1'1/4`` 会被判为同一个答案。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional, Sequence

from .expression import format_value
from .parser import ParseError, parse_expression, parse_value


@dataclass
class GradeDetail:
    """单题的批改明细。"""

    index: int
    expression: str
    submitted: str
    expected: str
    is_correct: bool
    note: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "index": self.index,
            "expression": self.expression,
            "submitted": self.submitted,
            "expected": self.expected,
            "is_correct": self.is_correct,
            "note": self.note,
        }


@dataclass
class GradeResult:
    """整份答卷的批改结果。"""

    details: List[GradeDetail] = field(default_factory=list)

    @property
    def correct_ids(self) -> List[int]:
        return [item.index for item in self.details if item.is_correct]

    @property
    def wrong_ids(self) -> List[int]:
        return [item.index for item in self.details if not item.is_correct]

    @property
    def total(self) -> int:
        return len(self.details)

    def to_grade_text(self) -> str:
        """生成 ``Grade.txt`` 的完整内容 (需求 9 要求的格式)。"""
        return (
            f"Correct: {len(self.correct_ids)} ({_join_ids(self.correct_ids)})\n"
            f"Wrong: {len(self.wrong_ids)} ({_join_ids(self.wrong_ids)})"
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "total": self.total,
            "correct_count": len(self.correct_ids),
            "wrong_count": len(self.wrong_ids),
            "correct_ids": self.correct_ids,
            "wrong_ids": self.wrong_ids,
            "correct_line": f"Correct: {len(self.correct_ids)} ({_join_ids(self.correct_ids)})",
            "wrong_line": f"Wrong: {len(self.wrong_ids)} ({_join_ids(self.wrong_ids)})",
            "details": [item.to_dict() for item in self.details],
        }


def _join_ids(ids: Sequence[int]) -> str:
    """把编号列表拼成 ``1, 3, 5`` 形式。"""
    return ", ".join(str(item) for item in ids)


def grade(exercise_lines: Sequence[str], answer_lines: Sequence[str]) -> GradeResult:
    """逐题批改 (题目文本无法解析时抛出 ParseError)。"""
    result = GradeResult()

    for position, exercise_line in enumerate(exercise_lines):
        index = position + 1
        try:
            expr = parse_expression(exercise_line)
        except ParseError as error:
            raise ParseError(f"第 {index} 行题目无法解析: {error}") from error

        expected_value = expr.evaluate()
        expected_text = format_value(expected_value)
        submitted_text = answer_lines[position] if position < len(answer_lines) else ""
        submitted_text = submitted_text.strip()

        if submitted_text == "":
            result.details.append(
                GradeDetail(index, exercise_line.strip(), "", expected_text, False, "未作答")
            )
            continue

        try:
            submitted_value: Optional[Fraction] = parse_value(submitted_text)
        except ParseError:
            submitted_value = None

        if submitted_value is None:
            result.details.append(
                GradeDetail(
                    index, exercise_line.strip(), submitted_text, expected_text, False,
                    "答案格式不规范",
                )
            )
        elif submitted_value == expected_value:
            result.details.append(
                GradeDetail(index, exercise_line.strip(), submitted_text, expected_text, True)
            )
        else:
            result.details.append(
                GradeDetail(
                    index, exercise_line.strip(), submitted_text, expected_text, False,
                    "答案错误",
                )
            )

    return result
