# SemFlow research contracts

独立包 `semflow-contracts`，只依赖锁定的 Pydantic；不初始化 Web、数据库、队列或配置。
契约源码与实现计划对应 [三内核数据协议](../../design/development/backend-decoupling-contracts-20261110.md)。

- `runs.py`：按 module / operation 两层判别的九种 RunSpec；策略、模型和 Prompt 显式冻结。
- `common.py`、`evidence.py`：内容寻址引用、源码清单、真实证据引用及使用方决策。
- `discovery.py`、`repair.py`、`rules.py`：三个模块的类型化输入、实体和技术结果。
- `actions.py`、`events.py`、`results.py`：批准 / 控制、追加事件、结果信封与不可变清单。
- `validation.py`：执行状态与检查状态分开；空检查、未执行或模型支持不能变成通过。

Python 调用：

```python
from semflow_contracts.runs import RUN_ADAPTER, validate_spec

spec = validate_spec(input_dict)
schema = RUN_ADAPTER.json_schema()
```

结构通过不等于源码、目标归属、工具环境或算法执行通过。运行时需继续核验产物字节、
源码快照和实际证据关联。科研 `execution_id` 与平台 audit / stage ID 没有隐含相等关系。

运行测试（从 `system/`）：

```sh
.venv/bin/pytest contracts/tests -q
```

当前包是迁移中的初版契约，未完成三内核真实工具验收；不要据此宣称独立科研链路已经可用。
