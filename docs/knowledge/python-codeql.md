# Python CodeQL 规则与动态执行审计知识

来源：项目维护的教学示例；API 依据固定 codeql/python-all@4.0.10。参考 https://codeql.github.com/docs/codeql-language-guides/codeql-library-for-python/ 与 https://codeql.github.com/docs/writing-codeql-queries/metadata-for-codeql-queries/ 。这是需要编译与样本验证的知识资料，不提供运行指令。

审计 Python eval / exec 动态执行时，区分常量与外部可控输入，查清 request.args、传播路径、保护措施和可达性。单纯出现 eval 不足以确认漏洞。基线 py/code-injection 使用数据流判断；补充规则应说明现有覆盖缺口，例如自定义框架输入源或封装汇点，再决定补模型、扩展查询或新查询。

用于演示规则验收的最小汇点查询：
```ql
/**
 * @name Dynamic eval review anchor
 * @description Identifies eval calls for manual input-control review.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id custom/dynamic-eval
 * @tags security external/cwe/cwe-095
 */
import python
from Call call, Name name
where call.getFunc() = name and name.getId() = "eval"
select call, "Dynamic execution requires input-control review."
```

它是复审锚点查询，不能声称所有命中都是漏洞。正例源码 `value = eval(input())` 的预期位置为第一行；安全反例 `value = int(input())` 不应命中。真实污点规则必须补充输入源、传播与消毒反例；确认样本覆盖后才能发布。自定义框架模型可保存在同一包中的 .qll 模块，并由薄查询调用。依赖和知识版本必须固定，编译通过后还需运行正反例。
