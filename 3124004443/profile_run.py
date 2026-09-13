# cProfile 性能剖析脚本：对核心算法采样，输出 profile_stats.prof / profile_results.txt
import cProfile
import pstats
from io import StringIO

from similarity import TextSimilarity


def generate_large_text(size):
    base = ("软件工程是一门研究用工程化方法构建和维护软件的学科，"
            "它涉及程序设计语言、数据库、软件开发工具、系统平台、"
            "标准、设计模式等方面。")
    repeat = (size // len(base)) + 1
    return base * repeat


def run_benchmark():
    original = generate_large_text(20000)
    plagiarized = original[:15000] + "这是后来被修改追加的内容句子。" * 200
    detector = TextSimilarity(n=2, method="cosine")
    return detector.compute(original, plagiarized)


def main():
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(5):
        run_benchmark()
    profiler.disable()

    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(15)
    with open("profile_results.txt", "w", encoding="utf-8") as handle:
        handle.write(stream.getvalue())

    stats.dump_stats("profile_stats.prof")
    print("profile done -> profile_results.txt / profile_stats.prof")


if __name__ == "__main__":
    main()
