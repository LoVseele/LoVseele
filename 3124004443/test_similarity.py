"""单元测试：覆盖正常场景、边界值、算法单元与命令行（CLI）异常分支。"""

# 测试函数以函数名自述用途，不再逐个编写 docstring
# pylint: disable=missing-function-docstring

import os
import subprocess
import sys
import tempfile

from main import main
from similarity import (build_vector, char_ngrams, cosine_similarity,
                        naive_cosine_similarity, simhash_similarity,
                        TextSimilarity)
from text_utils import normalize, read_text_file

ORIGINAL = "今天是星期天，天气晴，今天晚上我要去看电影。"
PLAGIARIZED = "今天是周天，天气晴朗，我晚上要去看电影。"


def test_identical_text():
    sim = TextSimilarity()
    assert abs(sim.compute(ORIGINAL, ORIGINAL) - 1.0) < 1e-9


def test_completely_different():
    sim = TextSimilarity()
    score = sim.compute("今天天气真好我们去公园玩吧",
                        "The quick brown fox jumps over the lazy dog")
    assert score < 0.05


def test_example_pair_range():
    sim = TextSimilarity()
    score = sim.compute(ORIGINAL, PLAGIARIZED)
    assert 0.5 < score < 0.97          # 示例对属于"大面积改写"，重复率应中等偏高


def test_empty_original():
    sim = TextSimilarity()
    assert sim.compute("", "今天是周天") == 0.0     # 空向量触发除零保护


def test_empty_plagiarism():
    sim = TextSimilarity()
    assert sim.compute("今天是星期天", "") == 0.0


def test_whitespace_ignored():
    sim = TextSimilarity()
    a = "今天 是 星期天 天气 晴"
    b = "今天是星期天天气晴"
    assert abs(sim.compute(a, b) - 1.0) < 1e-6      # 空白差异应被归一化消除


def test_punctuation_variation():
    sim = TextSimilarity()
    score = sim.compute("你好，世界。", "你好世界")
    assert score > 0.5


def test_single_char_added():
    sim = TextSimilarity()
    score = sim.compute("我爱北京天安门", "我爱北京天安门城楼")
    assert score > 0.8                              # 少量增字不应大幅拉低相似度


def test_substring_plagiarism():
    sim = TextSimilarity()
    a = "软件工程是一门研究用工程化方法构建和维护软件的学科"
    b = "软件工程是一门研究用工程化方法"
    assert sim.compute(a, b) > 0.7


def test_reversed_text_lower():
    sim = TextSimilarity()
    score = sim.compute("软件工程很有趣", "趣有很程工件事")
    assert score < 0.6                              # 语序被打乱，相似度应明显下降


def test_fullwidth_normalization():
    sim = TextSimilarity()
    score = sim.compute("ＡＢＣ１２３", "abc123")
    assert score > 0.9                              # 全角应被 NFKC 统一为半角


def test_char_ngrams_basic():
    assert list(char_ngrams("abc", 2)) == ["ab", "bc"]
    assert list(char_ngrams("a", 2)) == ["a"]       # 短于 n 时整体作为一个 gram
    assert len(list(char_ngrams("", 2))) == 0


def test_build_vector():
    vec = build_vector(["ab", "ab", "bc"])
    assert vec["ab"] == 2 and vec["bc"] == 1


def test_cosine_known_vectors():
    va = build_vector(["a", "a", "b"])
    vb = build_vector(["a", "b"])
    expected = 3 / (5 ** 0.5 * 2 ** 0.5)
    assert abs(cosine_similarity(va, vb) - expected) < 1e-9
    assert cosine_similarity(va, build_vector([])) == 0.0


def test_naive_equals_efficient():
    va = build_vector(char_ngrams("今天是星期天天气晴"))
    vb = build_vector(char_ngrams("今天是周天天气晴朗"))
    assert abs(cosine_similarity(va, vb) -
               naive_cosine_similarity(va, vb)) < 1e-9


def test_simhash_identical():
    assert simhash_similarity("软件工程很有趣", "软件工程很有趣") == 1.0


def test_simhash_discriminates():
    identical = simhash_similarity("软件工程很有趣", "软件工程很有趣")
    different = simhash_similarity("今天天气真好我们去公园玩吧",
                                   "The quick brown fox jumps over the lazy dog")
    assert identical == 1.0
    assert different < identical


def test_n_parameter_consistency():
    a = "软件工程是一门研究用工程化方法构建和维护软件的学科"
    for n in (1, 2, 3):
        assert abs(TextSimilarity(n=n).compute(a, a) - 1.0) < 1e-9


def test_main_cli_writes_answer():
    with tempfile.TemporaryDirectory() as tmp:
        op = os.path.join(tmp, "orig.txt")
        pp = os.path.join(tmp, "plag.txt")
        ap = os.path.join(tmp, "ans.txt")
        with open(op, "w", encoding="utf-8") as f:
            f.write(ORIGINAL)
        with open(pp, "w", encoding="utf-8") as f:
            f.write(PLAGIARIZED)
        assert main([op, pp, ap]) == 0
        with open(ap, "r", encoding="utf-8") as f:
            value = float(f.read().strip())
        assert 0.0 <= value <= 100.0


def test_main_missing_file_no_crash():
    with tempfile.TemporaryDirectory() as tmp:
        op = os.path.join(tmp, "nonexistent.txt")
        pp = os.path.join(tmp, "plag.txt")
        ap = os.path.join(tmp, "ans.txt")
        with open(pp, "w", encoding="utf-8") as f:
            f.write("hello")
        assert main([op, pp, ap]) == 0              # 缺失文件也不异常退出
        with open(ap, "r", encoding="utf-8") as f:
            assert f.read().strip() == "0.00"       # 兜底写出 0.00


def test_main_bad_argc():
    assert main(["only", "two"]) == 1


def test_main_wrong_arg_count_too_many():
    assert main(["a", "b", "c", "d"]) == 1


def test_normalize_none_returns_empty():
    assert normalize(None) == ""                    # 传入 None 时不应抛异常


def test_read_text_file_gbk():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "gbk.txt")
        with open(path, "wb") as f:
            f.write("今天是星期天".encode("gbk"))
        assert read_text_file(path) == "今天是星期天"   # 非 UTF-8 也能正确解码


def test_read_text_file_fallback_ignores_bad_bytes():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "broken.txt")
        with open(path, "wb") as f:
            f.write(b"\xff\x81abc")                 # 四种编码均无法解码
        assert read_text_file(path) == "abc"        # 兜底忽略坏字节而非崩溃


def test_naive_cosine_empty():
    assert naive_cosine_similarity(build_vector([]), build_vector([])) == 0.0


def test_simhash_method_via_compute():
    sim = TextSimilarity(method="simhash")
    assert abs(sim.compute(ORIGINAL, ORIGINAL) - 1.0) < 1e-9


def test_main_module_runs_as_script():
    project = os.path.dirname(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        op = os.path.join(tmp, "orig.txt")
        pp = os.path.join(tmp, "plag.txt")
        ap = os.path.join(tmp, "ans.txt")
        with open(op, "w", encoding="utf-8") as f:
            f.write(ORIGINAL)
        with open(pp, "w", encoding="utf-8") as f:
            f.write(PLAGIARIZED)
        result = subprocess.run([sys.executable, "main.py", op, pp, ap],
                                cwd=project, capture_output=True, check=False)
        assert result.returncode == 0               # 入口脚本真实可运行且正常退出
        with open(ap, "r", encoding="utf-8") as f:
            assert 0.0 <= float(f.read().strip()) <= 100.0


def test_main_unwritable_answer_path_no_crash():
    with tempfile.TemporaryDirectory() as tmp:
        op = os.path.join(tmp, "orig.txt")
        pp = os.path.join(tmp, "plag.txt")
        bad_answer = os.path.join(tmp, "missing_dir", "ans.txt")   # 目标目录不存在
        with open(op, "w", encoding="utf-8") as f:
            f.write(ORIGINAL)
        with open(pp, "w", encoding="utf-8") as f:
            f.write(PLAGIARIZED)
        assert main([op, pp, bad_answer]) == 0      # 连答案都写不出也不异常退出
