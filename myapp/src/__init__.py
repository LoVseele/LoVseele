# -*- coding: utf-8 -*-
"""核心算法包: 表达式 AST、题目生成、文本解析、批改与文件读写。

命令行入口 ``myapp.py`` 与 Web 后端 ``server.py`` 都只调用本包的接口。
"""

from .expression import BinaryOp, Expr, Number, format_value
from .fileio import (
    ANSWER_FILENAME,
    EXERCISE_FILENAME,
    GRADE_FILENAME,
    read_lines,
    write_grade_file,
    write_problem_files,
)
from .generator import (
    MAX_OPERATORS,
    ExpressionGenerator,
    Problem,
    ProblemGenerator,
    ProblemSet,
    describe_answer_type,
    validate_tree,
)
from .grader import GradeDetail, GradeResult, grade
from .parser import ParseError, parse_expression, parse_value

__all__ = [
    "ANSWER_FILENAME",
    "EXERCISE_FILENAME",
    "GRADE_FILENAME",
    "MAX_OPERATORS",
    "BinaryOp",
    "Expr",
    "ExpressionGenerator",
    "GradeDetail",
    "GradeResult",
    "Number",
    "ParseError",
    "Problem",
    "ProblemGenerator",
    "ProblemSet",
    "describe_answer_type",
    "format_value",
    "grade",
    "parse_expression",
    "parse_value",
    "read_lines",
    "validate_tree",
    "write_grade_file",
    "write_problem_files",
]

__version__ = "1.0.0"
