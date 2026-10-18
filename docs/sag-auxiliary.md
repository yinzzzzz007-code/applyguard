# SAG 辅助证据检索（本地实验接入）

本接入基于 [SAG 公开仓库](https://github.com/Zleap-AI/SAG) 的源限定搜索 API（核对版本 `a6f6a00f36ce0cbe43cd2fc0445b479e4ae4fff6`）。SAG 的完整 event–entity 检索引擎由独立的 `zleap-sag` 包提供，ApplyGuard 没有复制或重实现该引擎；这里通过其 REST 接口**实际调用 SAG 检索**。没有复制 SAG 原代码，因此不把接口适配误称为原代码移植。

## 边界

- `off`（默认）：原匹配输出原样返回。队友的证据 CRUD、`EvidenceMatcher` 评分、Claim Validator 和 Resume Selector 都未改。
- `shadow`：记录命中已有 Evidence ID 的 SAG 原文块；原分数、排序和选择不变。
- `rerank`：只对原本已经 `ready_for_selection`、无冲突且无缺口的匹配增加最多 0.06 的排序分；不改变证据 ID、强度、核验状态，也不把召回结果当成新的 Claim。该模式仅供后续对照评估，不代表已验证的精度提升。
- SAG 返回的 `content`、`summary` 不进入 Claim 或模型提示词，避免检索文本指令注入。只接受来源 ID、块 ID 和检索分数；原文须由用户在 SAG 中复核。
- SAG 不可用、映射冲突或配置不完整时回退原匹配。只允许本机 loopback HTTP，避免在配置失误时把 JD 发到外部服务。

## 启用

1. 单独运行本机 SAG，按其文档导入且索引用户**已同意使用**的证据材料。SAG 对外搜索需要登录令牌；不要把令牌、真实简历或原件提交到 Git。SAG 服务端可能为搜索摘要调用模型，需单独确认它的模型配置与数据流向。
2. 在 SAG 中确认信源 ID 和检索结果的 `chunk_id`。人工核对每个块确实对应 ApplyGuard 中同一候选人的已有证据，再在 Git 忽略的 `data/local/sag-evidence-map.json` 建立映射。例如：

```json
{
  "candidate_id": "cand_demo_001",
  "source_id": "SAG中的信源ID",
  "links": [
    {"chunk_id": "SAG返回的块ID", "evidence_id": "ev_repo_api"}
  ]
}
```

3. 在本机 `.env` 设置 `APPLYGUARD_SAG_MODE=shadow`、`APPLYGUARD_SAG_BASE_URL`、`APPLYGUARD_SAG_SOURCE_ID`、`APPLYGUARD_SAG_TOKEN`、`APPLYGUARD_SAG_MAPPING_PATH`。先用 `shadow` 核对溯源；要比较排序才显式改为 `rerank`。`data/local/` 和 `.env` 已由 Git 忽略。

适配层调用 `POST /api/v1/sources/{source_id}/search`，仅对已有匹配的 JD requirement 查询，使用 SAG 的 `multi` 策略、最多 8 个片段。只有同时满足来源匹配、候选人一致、块到 Evidence ID 映射唯一、证据已验证、证据属于该经历且已被基线匹配引用，命中才会进入 `sag_support`。JSON Schema 仅增加可选字段 `sag_auxiliary`、`sag_support`、`score_breakdown.sag_bonus`，旧输出仍有效。

## 尚未完成的验证

目前只有合成单元测试，**没有**用真实材料与权威数据集比较相关性、无依据 Claim 率、召回率、延迟或成本；也没有自动把本地证据 CRUD 内容同步进 SAG。不能据此宣称 ApplyGuard 已减少简历幻觉或提高群体上的 JD 匹配准确率。下一步按用户提供的数据集设计配对评测，并分别记录召回收益、误召回、人工核验成本、延迟和模型费用。
