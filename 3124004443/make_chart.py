"""根据 profile_stats.prof 生成「各函数累计耗时 Top-N」横向柱状图（SVG）。"""

import os
import pstats
from xml.sax.saxutils import escape

TOP_N = 12
WIDTH = 900
ROW_H = 34
PAD = 20


def build_rows(stats):
    """从剖析结果中取出 (标签, 累计耗时, 调用次数)，按累计耗时降序取前 N 条。"""
    rows = []
    for func, data in stats.stats.items():
        (_, ncalls, _, cumulative, _) = data
        source = func[0].replace("\\", "/")
        filename = "built-in" if source == "~" else os.path.basename(source)
        rows.append((f"{func[2]}  [{filename}]", cumulative, ncalls))
    rows.sort(key=lambda item: item[1], reverse=True)
    return rows[:TOP_N]


def render_svg(rows):
    """把数据行渲染为 SVG 字符串。"""
    max_value = max(item[1] for item in rows) if rows else 1.0
    height = PAD * 2 + 40 + ROW_H * len(rows)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{height}" font-family="Segoe UI, Arial, sans-serif">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{PAD}" y="24" font-size="16" font-weight="700" '
        f'fill="#1f2d3d">性能分析：各函数累计耗时（秒）</text>',
    ]
    y = PAD + 40
    for index, (label, value, ncalls) in enumerate(rows):
        bar_width = int((value / max_value) * (WIDTH - 360))
        color = "#e8543f" if index == 0 else "#2f6fed"
        # 函数名可能含 < > & 等 XML 保留字符，写入 SVG 前必须转义
        text = escape(f"{index + 1}. {label[:52]}")
        parts.append(f'<text x="{PAD}" y="{y + 16}" font-size="12" '
                     f'fill="#1f2d3d">{text}</text>')
        parts.append(f'<rect x="{PAD}" y="{y + 20}" width="{bar_width}" '
                     f'height="10" rx="3" fill="{color}"/>')
        parts.append(f'<text x="{PAD + bar_width + 6}" y="{y + 30}" '
                     f'font-size="11" fill="#555">{value:.3f}s · {ncalls} calls</text>')
        y += ROW_H
    parts.append('</svg>')
    return "\n".join(parts)


def main():
    """读取剖析数据，生成柱状图 SVG。"""
    stats = pstats.Stats("profile_stats.prof")
    svg = render_svg(build_rows(stats))
    with open("profile_chart.svg", "w", encoding="utf-8") as handle:
        handle.write(svg)
    print("chart written -> profile_chart.svg")


if __name__ == "__main__":
    main()
