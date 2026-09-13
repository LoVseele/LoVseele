# 根据 profile_stats.prof 生成函数累计耗时 Top-N 横向柱状图 (SVG)
import pstats

TOP_N = 12
WIDTH = 900
ROW_H = 34
PAD = 20


def main():
    stats = pstats.Stats("profile_stats.prof")
    rows = []
    for func, data in stats.stats.items():
        (_, ncalls, _, cumulative, _) = data
        filename = func[0].split("/")[-1]
        label = f"{func[2]}  [{filename}]"
        rows.append((label, cumulative, ncalls))
    rows.sort(key=lambda item: item[1], reverse=True)
    rows = rows[:TOP_N]

    max_val = max(item[1] for item in rows) if rows else 1.0
    chart_h = PAD * 2 + 40 + ROW_H * len(rows)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
           f'height="{chart_h}" font-family="Segoe UI, Arial, sans-serif">']
    svg.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    svg.append(f'<text x="{PAD}" y="24" font-size="16" font-weight="700" '
               f'fill="#1f2d3d">性能分析：各函数累计耗时 (秒)</text>')
    y = PAD + 40
    for idx, (label, val, ncalls) in enumerate(rows):
        bar_w = int((val / max_val) * (WIDTH - 360))
        color = "#e8543f" if idx == 0 else "#2f6fed"
        svg.append(f'<text x="{PAD}" y="{y + 16}" font-size="12" '
                   f'fill="#1f2d3d">{idx + 1}. {label[:40]}</text>')
        svg.append(f'<rect x="{PAD}" y="{y + 20}" width="{bar_w}" height="10" '
                   f'rx="3" fill="{color}"/>')
        svg.append(f'<text x="{PAD + bar_w + 6}" y="{y + 30}" font-size="11" '
                   f'fill="#555">{val:.3f}s · {ncalls} calls</text>')
        y += ROW_H
    svg.append('</svg>')
    with open("profile_chart.svg", "w", encoding="utf-8") as handle:
        handle.write("\n".join(svg))
    print("chart written -> profile_chart.svg")


if __name__ == "__main__":
    main()
