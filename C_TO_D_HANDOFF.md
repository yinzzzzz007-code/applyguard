# ApplyGuard C → D 技术交接

交接基线：`C` 分支从 B 的 `64cae15` 开始；C 交付版本标签为 `proposal-v0.3-ai-core`。此文档说明当前代码实际能做什么，以及 D 接前端、ATS 模拟器和人工确认时应使用的接口。详细验收证据见 `docs/C-requirements-audit.md`。

## 1. 本地启动与零费用演示

使用 Python 3.11+：

```sh
python -m pip install -r requirements.txt
python -B -m unittest discover -s tests -v
python -B -m demo.run_c_cases
python -m backend.app
```

`demo.run_c_cases` 固定模拟三个场景：正常匹配、无依据内容被阻止、模型超时后进入规则 Fallback。该命令从不请求模型服务，即使进程环境中已有 API Key。接口服务默认监听 `127.0.0.1:8000`。查看 `GET /health` 后，可调用：

```sh
curl -sS http://127.0.0.1:8000/api/v1/workflow/mock \
  -H 'Content-Type: application/json' \
  -d '{"candidate_id":"cand_demo_001","jd_text":"Backend Developer requires Python and automated tests.","parse_mode":"offline"}'
```

`parse_mode` 有三种值：`offline` 使用 C 规则解析，保证零 API 调用；`dynamic` 有 Key 时请求模型，无 Key 时转规则解析；`fixture` 返回 A/B 原固定演示。未传 `parse_mode` 时，为兼容旧版，无 Key 走固定演示，有 Key 走模型路径。D 的默认演示请求应显式使用 `offline`，否则输入 JD 可能没有被实际分析。

## 2. 九步响应如何呈现

固定顺序是 Career Vault → JD Parser → Evidence Matcher → Resume Selector → Claim Validator → ATS Form Mapper → Risk Check → Human Confirmation → Audit Record。读取 `step_trace` 的每一步状态；`component_modes.jd_parser` 标识 `MODEL`、`MODEL_SPAN_REPAIRED` 或 `RULE_FALLBACK`，`component_modes.ats_form_mapper` 当前恒为 `FIXTURE`。`MODEL_SPAN_REPAIRED` 表示模型引文不精确，C 从原 JD 找到确切片段并降低了置信度。

- `parsed_jd.requirements[]`：展示 `text`、`type`、`category` 和原文 `evidence_text`；该原文片段必须来自本次输入 JD。
- `evidence_match` 与 `resume_claims[]`：继续按 B 的结构展示匹配、保留/删除理由和证据 ID。被选中不等于已通过核验。
- `claim_verification[]`：按 `claim_id` 与简历内容关联，展示 `state`、`unsupported_fragments`、`explanation`、`support_score`。`VERIFIED` 只说明给定 Vault 元数据支持该原文，不等于外部事实已被独立证明。
- `ats_form_mapping`：目前由固定 fixture 提供，再由 C 根据核验结果限制每个字段 `action`。不要把它标成真实网页扫描结果。D 替换模拟映射时，须保留 `source_claim_ids` 的关联，并在字段值变化后重新核验/评估。
- `field_controls[]`：逐字段的 L0 普通建议、L1 展示证据来源、L2 歧义需人工确认、L3 敏感或严重问题需人工确认/阻止。它与整个申请的 `risk_result.risk_level` 是不同层级。`action == BLOCKED` 时禁止填写该字段，也不能靠确认按钮绕过。
- `risk_result`：`action == BLOCKED` 时禁用填写与确认，只允许编辑或取消；`REQUIRES_CONFIRMATION` 时展示理由并等待明确确认；`SAFE_TO_FILL` 仅表示可建议填写，绝不代表自动提交。
- `human_confirmation.allowed_actions`：当前后端只提供状态与动作建议；最终可操作的确认页面由 D 实现。求职申请最终提交必须由用户亲自操作，后端没有提交接口。
- `audit_record`：当前仅在响应中提供，在服务重启后不会持久保留。历史页面需等 A 的版本/存储接入。

`resume_claims[].evidence_ids` 可回查 `data/career-vault.seed.json` 中 `evidence_sources`。正式界面应同时展示证据名称、状态和为何支持当前主张；不能只显示“已验证”徽标。

## 3. 失败、缺项和测试接法

解析不了的 JD 返回 HTTP 422，统一错误格式为 `error.code/message/details/trace_id`；`error.details[0]` 含 `step_trace` 与 `audit_record`。下游模块执行错误可返回 500，也有九步轨迹：失败模块为 `FAILED`，尚未执行的步骤为 `SKIPPED`。前端应呈现错误、允许修改 JD 后重试，不应把失败画成空白的成功匹配。

无证据或夸大的 Claim 会变为 `BLOCKED` 并阻断其关联 ATS 字段；`NEEDS_REVIEW` 需要用户查看来源或修改后再次核验。缺失工作授权、薪资、法律声明等敏感字段由用户本人提供；不要从简历推断。实际 ATS 页面扫描、映射、自动填充、最终人工确认和提交前检查属于 D。C 当前只是后端模拟器，未接浏览器扩展或真实招聘站点。

D 可直接运行 `demo/run_c_cases.py` 取得三份响应，再根据 `workflow_status`、逐字段 `action` 和 `human_confirmation.allowed_actions` 设计正常、阻止、回退三个页面状态。测试页面时至少检查：`BLOCKED` 无确认/填充入口，`NEEDS_REVIEW` 有来源与原因，Fallback 状态有提示，最终提交始终由用户控制。

## 4. 模型配置：当前只是低成本测试默认值

默认 `APPLYGUARD_AI_MODEL=gpt-4o-mini`、`APPLYGUARD_AI_MAX_TOKENS=2048` 是目前为了控制课程测试费用采用的设置，**并非永久限制**。如需更好的解析效果，可在服务启动前改用当前服务商支持的更强模型，并适当调高最大输出 token；代码支持 1–16384，模型自身及服务商可能有更低或不同的限制。比如在 shell 中设置 `APPLYGUARD_AI_MODEL=<服务商支持的模型名>` 和 `APPLYGUARD_AI_MAX_TOKENS=4096`。实际成本会随模型、输入输出量和最多两次尝试而变化；更换模型后应重跑离线回归，并用独立 JD 数据检查质量，不能沿用旧模型的测量值。

模型请求使用 OpenAI 兼容的 `/chat/completions`、`response_format: json_object` 和 `max_tokens` 字段。换模型或服务商时先确认这些参数受支持；不兼容时需要调整 `backend/services/model_client.py` 的适配。无论使用哪个模型，解析结果都继续经过源文片段和 JSON Schema 校验，失败时最多重试一次，然后进入规则 Fallback 或安全停止。`APPLYGUARD_AI_API_KEY` 只放在本地 shell 环境或未跟踪的 `.env`；服务不会自动加载 `.env`，不要提交或在前端暴露密钥。

## 5. 尚待团队完成

B 的 Vault 是虚构只读数据；真实匿名访谈 Failure Cases 尚待 B 提供。A 负责持久化 Audit/Application Version 与最终集成。D 负责前端、ATS 模拟、敏感字段确认、可用性研究与演示视频。C 现有词典 Fallback 和规则核验是 Proposal 阶段安全基线，无法覆盖所有自然语言改写或替代外部事实核查。C 的全部文件、测试及已知限制分别见 `docs/C-delivery-manifest.md`、`docs/C-requirements-audit.md`、`docs/ai-evaluation-C.md`。
