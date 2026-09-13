import os
import tempfile

from similarity import (
    TextSimilarity,
    char_ngrams,
    build_vector,
    cosine_similarity,
    naive_cosine_similarity,
    simhash_similarity,
)
from main import main

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
    assert 0.5 < score < 0.97


def test_empty_original():
    sim = TextSimilarity()
    assert sim.compute("", "今天是周天") == 0.0


def test_empty_plagiarism():
    sim = TextSimilarity()
    assert sim.compute("今天是星期天", "") == 0.0


def test_whitespace_ignored():
    sim = TextSimilarity()
    a = "今天 是 星期天 天气 晴"
    b = "今天是星期天天气晴"
    assert abs(sim.compute(a, b) - 1.0) < 1e-6


def test_punctuation_variation():
    sim = TextSimilarity()
    score = sim.compute("你好，世界。", "你好世界")
    assert score > 0.5


def test_single_char_added():
    sim = TextSimilarity()
    score = sim.compute("我爱北京天安门", "我爱北京天安门城楼")
    assert score > 0.8


def test_substring_plagiarism():
    sim = TextSimilarity()
    a = "软件工程是一门研究用工程化方法构建和维护软件的学科"
    b = "软件工程是一门研究用工程化方法"
    assert sim.compute(a, b) > 0.7


def test_reversed_text_lower():
    sim = TextSimilarity()
    score = sim.compute("软件工程很有趣", "趣有很程工件事")
    assert score < 0.6


def test_fullwidth_normalization():
    sim = TextSimilarity()
    score = sim.compute("ＡＢＣ１２３", "abc123")
    assert score > 0.9


def test_char_ngrams_basic():
    assert char_ngrams("abc", 2) == ["ab", "bc"]
    assert char_ngrams("a", 2) == ["a"]
    assert char_ngrams("", 2) == []


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
    b = "软件工程是一门研究用工程化方法构建和维护软件的学科"
    for n in (1, 2, 3):
        assert abs(TextSimilarity(n=n).compute(a, b) - 1.0) < 1e-9


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
        assert main([op, pp, ap]) == 0  # 不异常退出
        with open(ap, "r", encoding="utf-8") as f:
            assert f.read().strip() == "0.00"


def test_main_bad_argc():
    assert main(["only", "two"]) == 1


def test_main_wrong_arg_count_too_many():
    assert main(["a", "b", "c", "d"]) == 1
