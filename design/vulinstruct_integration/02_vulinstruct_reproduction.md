# VulInstruct 独立复现

官方实现的 main 固定到 `7d2874b39efe81b5d4ee09ba5fdc5813b8272bc0`。其 README 区分了通用 CORRECT 规范库、Qwen 嵌入索引和领域 NVD 检索。官方代码声明 MIT 许可，所含各数据保留自身许可。公开 Hugging Face 数据版本为 `9527a9ac86c2345490f15e8d0ee8e051342bacf7`，Parquet 共 8,226,159 字节，SHA-256 为 `547a92376586cead9cff1ab63a817f6de8133d2464fd160ff871c9502785ee83`。实际分区为 1,491 条训练和 508 条测试。

独立检索只抽取训练行中明确标记为 statement 的通用约束。经过长度、标识及内容筛选后得到 439 条。其它推理、补丁、解决方案和测试数据字段都未进入索引。实际运行了一条关于请求、HTML 输出和编码的查询，BM25 返回 8 条，术语相关性门限保留 6 条，用时 0.0156 秒，模型调用为 0。原始回执位于 `D:/GPT/Outputs/SemFlow-VulInstruct/independent-query.json`。可复现工具和数据导出位于 `D:/GPT/Temp/semflow-vulinstruct`，原 Parquet 位于 `D:/GPT/Cache/vulinstruct`。

## 官方软件验证

固定提交下的 46 个源码、文档和测试文件都核对了 Git blob 摘要。随后获取了完整固定提交，官方数据清单的 12 个文件全部通过大小和 SHA-256 校验。官方版本为 0.5.7，核心无必需的外部包。通过 D 盘现有 Python 3.14 和 NumPy 执行 `python -m vulinstruct doctor` 与 `tools/smoke_pipeline.py --output ...`。烟测完成了 19 次替身调用、0 次网络模型调用，覆盖规范提取、通用索引、合成 NVD 索引、筛选、归纳、检测和评分。默认 Windows 编码下官方 pytest 为 127 通过、1 失败，失败项是发布扫描器未在测试文本中识别 CJK。用 UTF-8 模式复跑时 128 项均通过。日志保存在 `D:/GPT/Outputs/SemFlow-VulInstruct`。

| 环节 | 官方源码位置 |
| --- | --- |
| 代码理解、上下文关键词 | `src/vulinstruct/pipeline.py:194`，`Pipeline.run_sample` |
| 通用密集检索 | `src/vulinstruct/retrieval.py:104`，`DenseIndex.search`，默认 10 个候选 |
| 历史领域检索 | `src/vulinstruct/nvd.py` 的 `NVDIndex.search_domain` |
| 相关性筛选 | `src/vulinstruct/pipeline.py:66` 的 `selected_items`，默认 1–10 分，保留至少 6 分 |
| 领域规范与检测 | `Pipeline.run_sample` 中的归纳与检测分支，默认至少两个不同历史来源才归纳 |

通用索引使用固定 Qwen3-Embedding-0.6B。现有环境缺少 torch 和 transformers，未复跑论文语义向量索引。将原始上下文和补丁根因作为模型提示的做法没有接入。本地版本复用约束文本和可审计来源，基准测试仍需独立验证。

最初配置的 `qwen3.7-plus` 预检返回 HTTP 403 `AccessDenied.Unpurchased`。用户更新密钥后，原址和阿里云专属地址均返回 HTTP 200。SemFlow 真实对照另见测试结果。VulInstruct 官方 LLM 评分和真实领域 CVE 归纳未复现。现有关键词相关性筛选是本地可复现方案，效果不能与论文中的语义嵌入加模型评分等同。

Vul-RAG 的多维历史知识检索作为相关工作。其样本结构与当前仓库级消融的指标不互用。 [Vul-RAG 论文](https://arxiv.org/abs/2406.11147v3)

[官方实现](https://github.com/zhuhaopku/VulInstruct/tree/7d2874b39efe81b5d4ee09ba5fdc5813b8272bc0) · [官方数据说明](https://github.com/zhuhaopku/VulInstruct/blob/7d2874b39efe81b5d4ee09ba5fdc5813b8272bc0/docs/DATA.md) · [公开规范库](https://huggingface.co/datasets/hzhu721/vulnerability-specifications/tree/9527a9ac86c2345490f15e8d0ee8e051342bacf7)
