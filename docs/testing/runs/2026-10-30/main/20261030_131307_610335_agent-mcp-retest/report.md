# 测试报告：agent-mcp-retest

- 日期时间：2026-10-30T13:13:07.610335+08:00 — 2026-10-30T13:13:10.488885+08:00（北京时间）
- 范围：['tests.test_agent_mcp']
- 结果：FAIL；方法 2，通过 0，失败/错误 2，夹具错误 0，跳过 0。
- 参数子用例：4（不与测试方法相加冒充独立覆盖项）。
- 耗时：2.879秒。逐文件SHA256见report.json，完整执行信息见test.log。
- 限制：测试通过不等于无缺陷；模型桩测试不证明真实模型准确率。未执行项见测试计划。

| 测试 | 结果 | 秒 |
| --- | --- | ---: |
| tests.test_agent_mcp.MCPIntegrationTests.test_http_unauthorized_ui_and_invalid_token | FAIL | 0.594 |
| tests.test_agent_mcp.MCPIntegrationTests.test_protocol_exact_quotes_and_revocation | ERROR | 2.063 |
