# 论文查重（第一次个人编程作业）

用 Python 3 实现的「论文查重 / 文本相似度」程序：给定原文与抄袭版两个文件，
从命令行读入两个输入路径和一个输出路径，计算重复率（浮点，保留两位小数）并写入答案文件。

## 项目结构

```
3124004443/
├── main.py            # 程序入口：python main.py <原文> <抄袭版> <答案>
├── similarity.py      # 核心算法：字符 n-gram 余弦相似度 + SimHash 备选
├── text_utils.py      # 文本归一化与多编码文件读取
├── test_similarity.py # 单元测试（pytest，29 个用例）
├── requirements.txt   # 运行无第三方依赖；仅列出测试 / 质量工具
├── .pylintrc          # 代码质量分析配置
├── .coveragerc        # 覆盖率统计配置
├── profile_run.py     # 性能剖析与微基准脚本（开发用）
├── make_chart.py      # 由剖析数据生成性能图 SVG（开发用）
├── profile_chart.svg  # 性能分析图
├── sample/            # 样例：orig.txt（原文）/ orig_add.txt（抄袭版）/ ans.txt（答案）
└── BLOG.md            # 作业博客
```

## 使用方法

核心程序 `main.py` 仅依赖 Python 标准库，无需安装任何第三方包，直接运行即可：

```bash
# 计算重复率
python main.py "sample/orig.txt" "sample/orig_add.txt" "sample/ans.txt"
```

单元测试、覆盖率与代码质量分析依赖 pytest / pytest-cov / pylint，需先激活项目虚拟环境（工具已装于 `.venv`）：

```bash
# 激活虚拟环境（Windows）
.venv\Scripts\activate

# 单元测试 + 分支覆盖率
python -m pytest -q --cov=. --cov-branch --cov-report=term-missing

# 代码质量分析（目标：无警告）
python -m pylint text_utils.py similarity.py main.py

# 性能剖析与画图（开发用）
python profile_run.py && python make_chart.py
```

> 若不激活虚拟环境，可直接调用其解释器：`.venv\Scripts\python.exe -m pytest ...`。未激活时 `python` 指向系统解释器，因未安装上述工具会报 `No module named pytest`。

## 算法说明

1. **归一化**：NFKC 统一全 / 半角、转小写、去除所有空白，消除排版噪声。
2. **字符级 n-gram（默认 n=2）**：无需分词即可适配中文，对「增删改」都稳健。
3. **余弦相似度（默认）**：只在两向量的公共键上求点积，复杂度从 O(|A|·|B|) 降到 O(min(|A|,|B|))。
4. **SimHash（备选）**：O(n) 指纹 + 海明距离，可用 `method="simhash"` 切换，适合超长文档。
5. **惰性切分**：n-gram 用生成器逐个产出，避免为长文本一次性分配完整列表。

## 约束自查

- ✅ 仅使用标准库，全程不联网
- ✅ 只读取给定的两个输入文件、只写入给定的答案文件
- ✅ 任何异常都被兜底处理并写出 `0.00`，不会异常退出
- ✅ 单次计算约 15 ms（20 000 字符文本），内存远低于 2048 MB
- ✅ pylint 10.00/10 无警告；29 个单元测试全部通过，语句与分支覆盖率 100%
