# 论文查重（第一次个人编程作业）

使用 **Python 3** 实现的「论文查重 / 文本相似度」程序。给出原文文件与抄袭版论文文件，
从命令行读取两个输入路径与一个输出路径，计算重复率（浮点，保留两位小数）并写入答案文件。

> ⚠️ 提交前请将本项目整体放入以你**学号命名**的文件夹，再推送到你的 GitHub 仓库。

## 项目结构

```
<学号>/
├── main.py            # 程序入口：python main.py <原文> <抄袭版> <answer>
├── similarity.py      # 核心算法：字符 n-gram 余弦相似度 + SimHash
├── text_utils.py      # 文本归一化与文件读取
├── test_similarity.py # 单元测试（pytest，23 个用例）
├── requirements.txt   # 运行无第三方依赖；列测试/质量工具
├── .pylintrc          # 代码质量分析配置（目标：0 警告）
├── .coveragerc        # 覆盖率统计配置
├── profile_run.py     # 性能剖析脚本（开发用，不随作业运行）
├── make_chart.py      # 由剖析数据生成性能图 SVG（开发用）
├── profile_results.txt / profile_stats.prof / profile_chart.svg
├── sample/            # 样例：orig.txt（原文）/ orig_add.txt（抄袭版）/ ans.txt（答案）
├── PSP.md             # PSP 个人开发流程表
├── BLOG.md            # 博客草稿（覆盖 60 分博客评分全部要点）
```

## 使用方法

```bash
# 计算重复率
python main.py "C:/tests/orig.txt" "C:/tests/orig_add.txt" "C:/tests/ans.txt"

# 运行单元测试 + 分支覆盖率
python -m pytest -q --cov=. --cov-branch --cov-report=term-missing

# 代码质量分析（目标：无警告）
python -m pylint text_utils.py similarity.py main.py

# 性能剖析（开发用）
python profile_run.py
python make_chart.py   # 生成 profile_chart.svg
```

## 算法说明（简述）

1. **归一化**：NFKC 统一全/半角、转小写、去除所有空白，对空白与全角差异鲁棒。
2. **字符级 n-gram（默认 n=2）**：不依赖分词，天然适配中文；对「增删改」都稳健。
3. **余弦相似度（默认）**：只遍历两向量的公共 key，时间复杂度 O(min(|A|,|B|))。
4. **SimHash（备援）**：O(n) 指纹算法，适合超长文档，可用 `method="simhash"` 切换。

## 评分约束自查

- ✅ 不联网（仅标准库）
- ✅ 只读取给定的两个输入文件、只写入给定的答案文件
- ✅ 异常被捕获并写出 `0.00`，不会异常退出
- ✅ 单次计算远低于 5 秒、内存远低于 2048 MB
- ✅ pylint 10.00/10，无警告；单元测试 22 passed，源码分支覆盖率 91%
