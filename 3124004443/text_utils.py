"""文本预处理：归一化与多编码容错读取。"""

import re
import unicodedata


def normalize(text):
    """把文本统一成可比较的规范形式：NFKC（全角转半角）、转小写、去除所有空白。

    归一化的目的是消除"全角/半角、大小写、空格与换行"这类表面差异，
    让相似度只反映真正的文字内容，而不被排版噪声干扰。
    """
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    return re.sub(r"\s+", "", text)


def read_text_file(path):
    """按常见中文编码顺序读取文本，尽量避免因编码不一致而读取失败。

    依次尝试 utf-8 / utf-8-sig / gbk / gb18030；只有当解码失败时才换下一种，
    文件不存在等 IO 错误则直接抛出，交由上层统一兜底处理。
    """
    encodings = ("utf-8", "utf-8-sig", "gbk", "gb18030")
    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as handle:
                return handle.read()
        except UnicodeDecodeError:
            continue
    # 最后兜底：忽略无法解码的个别字节，保证有内容可比而不是直接失败
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        return handle.read()
