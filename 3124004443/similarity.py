"""核心算法：字符 n-gram 余弦相似度，并提供 SimHash 作为超长文本的备选方案。"""

import hashlib
import math
from collections import Counter

from text_utils import normalize


def char_ngrams(text, n=2):
    """按滑动窗口惰性切分字符 n-gram。

    用生成器逐个产出，避免为长文本一次性分配完整的 gram 列表，降低峰值内存；
    文本为空时产出空序列，长度不足 n 时把整段文本作为一个 gram。
    """
    if not text:
        return
    if len(text) < n:
        yield text
        return
    for i in range(len(text) - n + 1):
        yield text[i:i + n]


def build_vector(tokens):
    """把 gram 序列统计成「gram -> 出现次数」的词频向量。"""
    return Counter(tokens)


def _cosine(numerator, vec_a, vec_b):
    """由点积与两向量模长计算余弦值，任一向量模长为 0（空向量）时返回 0.0。"""
    norm_a = math.sqrt(sum(value * value for value in vec_a.values()))
    norm_b = math.sqrt(sum(value * value for value in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return numerator / (norm_a * norm_b)


def cosine_similarity(vec_a, vec_b):
    """基于向量交集的余弦相似度。

    只遍历两个向量的公共键，复杂度 O(min(|A|, |B|))，远优于双重循环的 O(|A|·|B|)。
    """
    common = vec_a.keys() & vec_b.keys()
    numerator = sum(vec_a[gram] * vec_b[gram] for gram in common)
    return _cosine(numerator, vec_a, vec_b)


def naive_cosine_similarity(vec_a, vec_b):
    """朴素双重循环版本的余弦，仅用于校验优化前后结果一致并做耗时对照。"""
    numerator = sum(
        count_a * count_b
        for gram_a, count_a in vec_a.items()
        for gram_b, count_b in vec_b.items()
        if gram_a == gram_b
    )
    return _cosine(numerator, vec_a, vec_b)


def _stable_hash(token, bits=64):
    """用 MD5 计算 token 的稳定哈希值，不依赖 PYTHONHASHSEED，保证每次运行结果一致。"""
    digest = hashlib.md5(token.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return value & ((1 << bits) - 1)


def simhash(text, n=2, bits=64):
    """计算文本的 SimHash 指纹：每个 gram 哈希后逐位投票，得到 bits 位签名。"""
    vector = [0] * bits
    for gram in char_ngrams(text, n):
        hashed = _stable_hash(gram, bits)
        for i in range(bits):
            vector[i] += 1 if (hashed >> i) & 1 else -1
    fingerprint = 0
    for i in range(bits):
        if vector[i] > 0:
            fingerprint |= 1 << i
    return fingerprint


def simhash_similarity(text_a, text_b, n=2, bits=64):
    """用两个 SimHash 指纹的海明距离衡量相似度，完全相同为 1.0。"""
    fingerprint_a = simhash(text_a, n, bits)
    fingerprint_b = simhash(text_b, n, bits)
    distance = bin(fingerprint_a ^ fingerprint_b).count("1")
    return 1.0 - distance / bits


class TextSimilarity:
    """对外统一的查重接口：先归一化，再按 method 选择具体相似度算法。"""

    def __init__(self, n=2, method="cosine"):
        self.n = n
        self.method = method

    def compute(self, original, plagiarized):
        """返回 [0, 1] 的相似度；cosine 为默认方案，simhash 可作超长文本备选。"""
        norm_a = normalize(original)
        norm_b = normalize(plagiarized)
        if self.method == "simhash":
            return simhash_similarity(norm_a, norm_b, self.n)
        vec_a = build_vector(char_ngrams(norm_a, self.n))
        vec_b = build_vector(char_ngrams(norm_b, self.n))
        return cosine_similarity(vec_a, vec_b)
