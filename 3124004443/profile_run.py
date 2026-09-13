"""开发用性能脚本：微观对比两种余弦实现，并用 cProfile 剖析完整查重流程。"""

import cProfile
import pstats
import random
import time
from io import StringIO

from similarity import (build_vector, char_ngrams, cosine_similarity,
                        naive_cosine_similarity, TextSimilarity)
from text_utils import normalize

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


def run_pipeline(size=20000):
    """跑一次完整查重：原文 vs（截断后追加内容的）抄袭版。"""
    original = repeat_text(size)
    plagiarized = original[:int(size * 0.75)] + "这是后来被修改追加的内容句子。" * 200
    return TextSimilarity(n=2, method="cosine").compute(original, plagiarized)


def profile_pipeline(rounds=5):
    """用 cProfile 采样完整流程，输出 profile_results.txt 与 profile_stats.prof。"""
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(rounds):
        run_pipeline()
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
    """先跑微基准对比，再对完整流程做 cProfile 采样。"""
    micro_benchmark()
    profile_pipeline()


if __name__ == "__main__":
    main()
