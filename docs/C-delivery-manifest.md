# C 交付文件清单与最终检查

当前分支 `C`，基线 `64cae15`，共 28 个新增或修改文件。交付在独立 C 分支与 `proposal-v0.3-ai-core` 标签；main/B 未合并。

- `.env.example`
- `C_TO_D_HANDOFF.md`
- `HANDOFF.md`
- `README.md`
- `THIRD_PARTY_NOTICES.md`
- `backend/app.py`
- `backend/services/claim_validator.py`
- `backend/services/jd_parser.py`
- `backend/services/model_client.py`
- `backend/services/prompts.py`
- `backend/services/risk_engine.py`
- `backend/services/schema_validation.py`
- `backend/services/skill_router.py`
- `backend/services/third_party/resume_matcher_keywords.py`
- `demo/run_c_cases.py`
- `docs/C-delivery-manifest.md`
- `docs/C-requirements-audit.md`
- `docs/ai-evaluation-C.md`
- `docs/architecture.md`
- `docs/interface-contracts.md`
- `docs/user-study/C-failure-case-review.md`
- `eval/c_benchmark.py`
- `eval/c_cases.json`
- `eval/results/c-offline-audit.json`
- `presentation/slide-content-C.md`
- `requirements.txt`
- `tests/test_c_audit.py`
- `tests/test_member_c.py`

最终完整回归：76/76 通过（A/B 29 项原样保留）；`git diff --check` 通过；修改/新增文件的凭据模式扫描无命中。contracts、data、A/B tests、B Vault/Matcher/Selector、B ASu vendor 均无修改。

本机实际验证命令：

```sh
python -B -m unittest discover -s tests -q
```

其他环境用 Python 3.11+ 安装 `requirements.txt` 后执行 README 的标准命令，不依赖此机器路径。测试里的本机 HTTP 服务器使用临时端口；模型调用全部离线或模拟。

直接复用记录见 `THIRD_PARTY_NOTICES.md`：Resume Matcher 固定 `9c05e423dfde44a5b4bb398d2dc7507194252ded`，Apache-2.0，JD sanitization/list helpers 原函数保持不变；C 自行编写适配、来源核查、模型封装与风险规则。B 的 ASu `fail`/`validate_metric` 来自固定 `f460582b1a48c7770496d7999ae3a14a2ce0452b`，MIT，C 调用既有算术适配层，未重复复制。Plan-Then-Execute 未复制，使用自行实现的九步 Router。

交接要求和未完成的团队阶段事项见 `C-requirements-audit.md`；此次审计没有新增付费调用。
