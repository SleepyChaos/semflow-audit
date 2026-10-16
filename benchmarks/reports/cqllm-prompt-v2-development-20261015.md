# 无RAG提示v2开发验证结果

2026-10-15 16:49（北京时间）完成。固定12项、12类CWE；同模型、同依赖、同最多两轮编译反馈；正式全量v1成绩保留。

| 提示版本 | 首轮编译通过 | 最终编译通过 |
|---|---:|---:|
| v1历史同任务 | 0/12（0%） | 1/12（8.33%） |
| v2独立新调用 | 8/12（66.67%） | 10/12（83.33%） |

最终通过净增9条，75个百分点：10条原失败转通过，1条原通过转失败，1条两版均失败。这个结果说明固定输出契约和通用新版API提示能明显改善本批编译可用性；不能外推为完整298项83.33%，也不能视为检测正确率。

| 任务 | CWE | v1最终 | v2首轮 | v2最终 |
|---|---|---|---|---|
| row-0172 | CWE-79 | False | True | True |
| row-0149 | CWE-611 | False | True | True |
| row-0199 | CWE-326 | True | False | False |
| row-0141 | CWE-601 | False | True | True |
| row-0033 | CWE-74 | False | False | True |
| row-0296 | CWE-120 | False | True | True |
| row-0208 | CWE-522 | False | True | True |
| row-0203 | CWE-400 | False | True | True |
| row-0077 | CWE-116 | False | False | False |
| row-0188 | CWE-203 | False | False | True |
| row-0102 | CWE-287 | False | True | True |
| row-0064 | CWE-89 | False | True | True |

新调用账本：{'calls': 16, 'input_tokens': 27861, 'output_tokens': 9618}；用量未知调用0条。

剩余失败：row-0199使用不存在的Expr.getConstantValue()；row-0077把string转换为Name，均在两轮预算内未修正。原来能通过的row-0199本轮失败，须保留回退，不择优拼接两版结果。

本轮只评估编译，未执行作者数据库或正反例；人工检查还发现部分生成规则source/sink建模粗糙，编译通过不能证明语义正确。没有将通用提示中的API指导称为任务检索，没有注入作者答案；新提示长度增加，属于改动因素。

这是已参与开发的12条需求，不是独立留出测试。后续正式v2全量应两组都用同一新版提示并单独冻结；不能把v2无RAG开发成绩直接与v1全量RAG混成消融结论。保持当前v1与已安排Vul4Py接续顺序。

协议：[开发方案](../experiments/cqllm-prompt-v2-development-20261015.md)。原始账本：artifacts/research/cqllm/20261015-prompt-v2-pilot；任务、提示和脚本哈希均在protocol.json。
