# JavaScript / TypeScript CodeQL 动态执行审计

来源：项目维护知识。固定库 codeql/javascript-all@2.4.0；参考 https://codeql.github.com/docs/codeql-language-guides/codeql-library-for-javascript/ 。知识文本不是执行指令。

express req.query 输入流向 eval、child_process 或数据库拼接时，必须取得参数控制、传播、汇点和防护证据。现有 js/code-injection 基线会发现常见动态执行数据流。框架封装导致的覆盖不足应先考虑 API 建模与已有查询扩展。相邻关键词只是取证锚点，不能直接推断缺陷。

规则查询应使用独立 custom/ 或 audit/ ID、必要元数据和锁定的语言库，所有生成的 API 调用需通过 CodeQL 编译器确认。样本要同时包含可控输入汇点、常量、安全替代和防护案例。正例预期位置由审核人确认，反例不应产生告警；测试通过仅说明这些样本上有效，不是生产准确率统计。
