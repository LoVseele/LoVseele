"""开发用性能脚本：在真实测试文本上做端到端基准，并用 cProfile 剖析查重流程。"""

import cProfile
import os
import pstats
import random
import time
from io import StringIO

from similarity import (build_vector, char_ngrams, cosine_similarity,
                        naive_cosine_similarity, TextSimilarity)
from text_utils import normalize, read_text_file

SAMPLE_DIR = "sample"
ORIGIN_PATH = os.path.join(SAMPLE_DIR, "orig.txt")
PLAGIARISM_PATH = os.path.join(SAMPLE_DIR, "orig_0.8_dis_15.txt")

BASE = ("软件工程是一门研究用工程化方法构建和维护软件的学科，"
        "它涉及程序设计语言、数据库、软件开发工具、系统平台、"
        "标准、设计模式等方面。")
CHAR_POOL = "".join(chr(0x4E00 + i) for i in range(3000))


def repeat_text(size):
    """用固定语料重复拼接出约 size 个字符的文本（低熵，公共 gram 较多）。"""
    return (BASE * (size // len(BASE) + 1))[:size]


def random_text(size, seed=2024):
    """生成高熵随机文本：字符几乎互不重复，使公共键数量接近上界，便于压测最坏情况。"""
    generator = random.Random(seed)
    return "".join(generator.choice(CHAR_POOL) for _ in range(size))


def load_real_pair():
    """读取 sample/ 下的真实测试文本；两者缺失时退回合成的低熵文本。"""
    if os.path.isfile(ORIGIN_PATH) and os.path.isfile(PLAGIARISM_PATH):
        return read_text_file(ORIGIN_PATH), read_text_file(PLAGIARISM_PATH)
    return repeat_text(20000), repeat_text(20000)[:15000] + "追加的句子。" * 200


def real_benchmark(rounds=5):
    """在真实测试文本上测量「读取文件 + 查重」的端到端单次耗时。"""
    original, plagiarized = load_real_pair()
    detector = TextSimilarity(n=2, method="cosine")
    start = time.perf_counter()
    for _ in range(rounds):
        original, plagiarized = load_real_pair()
        similarity = detector.compute(original, plagiarized)
    elapsed = (time.perf_counter() - start) / rounds
    print(f"[真实文本] 原文 {len(original)} 字 vs 改写版 {len(plagiarized)} 字"
          f"，相似度 {similarity * 100:.2f}%")
    print(f"  读取 + 查重 单次耗时: {elapsed * 1000:.1f} ms（共 {rounds} 次平均）")


def micro_benchmark(sizes=(300, 600), rounds=30):
    """对比两种余弦在不同规模高熵文本上的单次耗时，观察各自的复杂度趋势。"""
    print("[微基准] 高熵文本（去重后 gram 数接近文本长度，放大两者的复杂度差异）")
    for size in sizes:
        vec_a = build_vector(char_ngrams(normalize(random_text(size))))
        vec_b = build_vector(char_ngrams(normalize(random_text(size, seed=7))))

        start = time.perf_counter()
        for _ in range(rounds):
            cosine_similarity(vec_a, vec_b)
        efficient = (time.perf_counter() - start) / rounds

        start = time.perf_counter()
        for _ in range(rounds):
            naive_cosine_similarity(vec_a, vec_b)
        naive = (time.perf_counter() - start) / rounds

        print(f"  {size:>3} 字符: 交集 {efficient * 1000:.4f} ms | "
              f"朴素 {naive * 1000:.4f} ms | 提速 {naive / efficient:.0f}x")


def profile_pipeline(rounds=5):
    """在真实文本上对查重流程做 cProfile 采样，输出结果文件与统计数据。"""
    original, plagiarized = load_real_pair()
    detector = TextSimilarity(n=2, method="cosine")

    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(rounds):
        detector.compute(original, plagiarized)
    profiler.disable()

    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(15)
    with open("profile_results.txt", "w", encoding="utf-8") as handle:
        handle.write(stream.getvalue())
    stats.dump_stats("profile_stats.prof")
    print("[剖析] 已生成 profile_results.txt / profile_stats.prof")


def main():
    """依次执行：真实文本端到端基准、两种余弦的微基准、查重流程的 cProfile 剖析。"""
    real_benchmark()
    micro_benchmark()
    profile_pipeline()


if __name__ == "__main__":
    main()
