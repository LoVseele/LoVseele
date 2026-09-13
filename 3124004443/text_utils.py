import re
import unicodedata


def normalize(text):
    if text is None:
        return ""
    # NFKC 归一化（全角→半角）+ 小写 + 去空白，避免分词依赖
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    return text


def read_text_file(path):
    encodings = ("utf-8", "utf-8-sig", "gbk", "gb18030")
    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as handle:
                return handle.read()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    # 兜底：忽略无法解码的字节，保证任意文件下都不崩溃
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        return handle.read()
