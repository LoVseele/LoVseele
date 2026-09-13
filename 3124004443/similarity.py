import hashlib
import math
from collections import Counter

from text_utils import normalize


def char_ngrams(text, n=2):
    if not text:
        return []
    if len(text) < n:
        return [text]
    return [text[i:i + n] for i in range(len(text) - n + 1)]


def build_vector(tokens):
    return Counter(tokens)


def cosine_similarity(vec_a, vec_b):
    # 基于交集的余弦：只遍历公共 key，复杂度 O(min(|A|,|B|))，远快于双重循环
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a) & set(vec_b)
    numerator = sum(vec_a[token] * vec_b[token] for token in common)
    mag_a = math.sqrt(sum(value * value for value in vec_a.values()))
    mag_b = math.sqrt(sum(value * value for value in vec_b.values()))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return numerator / (mag_a * mag_b)


def naive_cosine_similarity(vec_a, vec_b):
    # 朴素双重循环，仅用于性能对比
    numerator = 0.0
    for token_a, count_a in vec_a.items():
        for token_b, count_b in vec_b.items():
            if token_a == token_b:
                numerator += count_a * count_b
    mag_a = math.sqrt(sum(value * value for value in vec_a.values()))
    mag_b = math.sqrt(sum(value * value for value in vec_b.values()))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return numerator / (mag_a * mag_b)


def _stable_hash(token, bits=64):
    # 用 hashlib，不受 PYTHONHASHSEED 影响
    digest = hashlib.md5(token.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return value & ((1 << bits) - 1)


def simhash(text, n=2, bits=64):
    vector = [0] * bits
    for gram in char_ngrams(text, n):
        hashed = _stable_hash(gram, bits)
        for i in range(bits):
            if (hashed >> i) & 1:
                vector[i] += 1
            else:
                vector[i] -= 1
    fingerprint = 0
    for i in range(bits):
        if vector[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def simhash_similarity(text_a, text_b, n=2, bits=64):
    fa = simhash(text_a, n, bits)
    fb = simhash(text_b, n, bits)
    distance = bin(fa ^ fb).count("1")
    return 1.0 - distance / bits


class TextSimilarity:
    def __init__(self, n=2, method="cosine"):
        self.n = n
        self.method = method

    def compute(self, original, plagiarized):
        norm_a = normalize(original)
        norm_b = normalize(plagiarized)
        if self.method == "simhash":
            return simhash_similarity(norm_a, norm_b, self.n)
        vec_a = build_vector(char_ngrams(norm_a, self.n))
        vec_b = build_vector(char_ngrams(norm_b, self.n))
        return cosine_similarity(vec_a, vec_b)
