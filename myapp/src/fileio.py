# -*- coding: utf-8 -*-
"""Exercises.txt / Answers.txt / Grade.txt 的读写 (UTF-8, 行号一一对应)。"""

from __future__ import annotations

import os
from typing import Iterable, List

#: 题目文件 / 答案文件 / 成绩文件的固定名称 (需求 7、8、9)
EXERCISE_FILENAME = "Exercises.txt"
ANSWER_FILENAME = "Answers.txt"
GRADE_FILENAME = "Grade.txt"


def read_lines(path: str, keep_empty: bool = False) -> List[str]:
    """读取文本文件的所有行 (去掉行尾换行符)。

    ``keep_empty`` 为 ``False`` 时跳过空行, 适用于题目文件; 读取**答案文件**
    必须传 ``True`` —— 空行代表"该题未作答", 若被跳过, 它后面的答案就会
    整体前移一行, 与题目错位。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        lines = [line.rstrip("\n") for line in handle]
    if keep_empty:
        return lines
    return [line for line in lines if line.strip() != ""]


def write_lines(path: str, lines: Iterable[str]) -> str:
    """把若干行写入文件, 返回绝对路径。"""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for line in lines:
            handle.write(f"{line}\n")
    return os.path.abspath(path)


def write_problem_files(output_dir: str, exercise_lines: List[str], answer_lines: List[str]):
    """写出 ``Exercises.txt`` 与 ``Answers.txt``, 返回两个文件的绝对路径。"""
    exercise_path = write_lines(os.path.join(output_dir, EXERCISE_FILENAME), exercise_lines)
    answer_path = write_lines(os.path.join(output_dir, ANSWER_FILENAME), answer_lines)
    return exercise_path, answer_path


def write_grade_file(output_dir: str, content: str) -> str:
    """写出 ``Grade.txt``, 返回其绝对路径。"""
    return write_lines(os.path.join(output_dir, GRADE_FILENAME), content.splitlines())
