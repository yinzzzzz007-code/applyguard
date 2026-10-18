# FELM / CRAG 小样本测试报告

日期：2026-10-18  
范围：Proposal 阶段探索性评测；不是完整基准测试，也不是用户研究结果。

## 结论摘要

- FELM 20 条片段中，10 条是原始标注为事实错误且带纠错注释的片段，10 条是事实片段。按本报告的合成适配方式输入现有 `ClaimValidator` 后，7/10 错误片段仍被标为 `VERIFIED`，3/10 进入 `NEEDS_REVIEW`；正确片段 9/10 为 `VERIFIED`，1/10 为 `NEEDS_REVIEW`。本轮未出现 `BLOCKED`。
- 这暴露了明确缺口：当前验证器能检查 Claim 与 Vault 的 ID、状态和结构关系，但对“证据文字是否支持或反驳未改写 Claim”缺少一般性语义判断。上述 70% 错误放行率只适用于本次合成测试夹具，不可解释为 ApplyGuard 真实简历用户的错误率。
- CRAG 10 条示例问答被作为跨领域干扰问题送入 ApplyGuard 虚构 Career Vault：0 条产生匹配、0 条可选匹配，10 条均保持未覆盖。它只说明当前基线在这 10 个问题上没有误用无关经历；不证明真实 JD 的匹配准确率。
- 本次没有连接运行中的 SAG 或索引证据，因此没有测出 SAG 对上述指标的提升。FELM 和 CRAG 都不是简历—JD 配对数据集，不能单独证明 JD 匹配有效，也不能证明真实用户中的幻觉减少。

## 数据与抽样

| 数据集 | 来源 / 版本 | 抽样方法 | 许可与留存 |
|---|---|---|---|
| FELM | [官方代码仓库](https://github.com/hkust-nlp/felm)，数据读取脚本指向 [Hugging Face `sjtu-lit/felm`](https://huggingface.co/datasets/sjtu-lit/felm)；本轮数据归档 SHA-256：`9f9ed5557eec67e038d129b9141565680a556c9819f95b2c0bcc453cdc9b516e` | 使用固定随机种子 `20261018`，在 world knowledge、science、math、reasoning、writing/recommendation 五个子集各取 2 个事实错误片段与 2 个事实片段，共 20 条。错误片段要求有数据集纠错注释。 | 数据集为 CC BY-NC-SA 4.0。归档只在内存中读取，没有把原始数据复制进 ApplyGuard。reasoning 子集有 7 条记录的片段、标签、注释长度无法对齐，排除；其他四个子集未因此排除记录。许可与数据字段见 [FELM README](https://github.com/hkust-nlp/felm#readme)。 |
| CRAG | [官方仓库](https://github.com/facebookresearch/CRAG)，本机提交 `ad1518887dd4d9ebcd7de95388c7a62751e7705c` 的 `example_data/dev_data.jsonl.bz2`；SHA-256：`81b1902691625e3837346a4d3e446d74add4e8bf837db520df833b19e5a1de07` | 使用仓库内全部 10 条示例。包含 finance 3、movie 3、open 3、sports 1；含 comparison、multi-hop、set、simple、false-premise 等问题类型。将 QA 问题作为与候选经历无关的干扰 requirement。 | 仓库声明 CC BY-NC 4.0。压缩文件留在仓库克隆目录，没有复制到 ApplyGuard。数据字段与来源见 [CRAG Dataset Documentation](https://github.com/facebookresearch/CRAG/blob/main/docs/dataset.md)。 |

FELM 数据归档虽仅约 260 KB，本轮仍只选择并评测 20 个片段。报告仅留样本编号和聚合状态，不保留原始回答文本。

## FELM：Claim 事实性核验压力测试

### 适配方式

FELM 片段被原样作为合成 Career Vault Claim。对事实错误片段，证据描述使用 FELM 对应的人工纠错注释；对事实片段，证据描述使用该事实片段本身。所有合成证据均设为已验证，以便观察现有 `ClaimValidator` 是否会比较 Claim 与其关联文字。未提供真实 Vault、真实简历或真实来源文件。

该方式是针对“文字证据冲突检查”的受控压力测试，不是 FELM 原论文评测流程。FELM 的错误注释也不等同于 ApplyGuard 用户提交的原始证据。

### 结果

| FELM 标注 | 样本数 | `VERIFIED` | `NEEDS_REVIEW` | `BLOCKED` |
|---|---:|---:|---:|---:|
| 事实错误 | 10 | 7 | 3 | 0 |
| 事实正确 | 10 | 9 | 1 | 0 |

如果仅把 `VERIFIED` 视为放行，错误片段放行率为 7/10（70%），事实片段放行率为 9/10（90%）。因此，本轮观察到的错误放行率高，不能把当前结构核验理解成通用事实判别器。`NEEDS_REVIEW` 表示交由用户检查，不等同于自动识别出事实错误。

### 可复现样本编号

格式为 `子集:记录编号:片段序号`；片段序号从 0 开始。`E` 表示 FELM 标注事实错误，`F` 表示事实片段。

| 子集 | 事实错误样本 | 事实片段样本 |
|---|---|---|
| world knowledge (`wk`) | `111:0` → VERIFIED；`38:9` → VERIFIED | `176:1` → VERIFIED；`152:1` → NEEDS_REVIEW |
| science | `1:3` → NEEDS_REVIEW；`11:0` → VERIFIED | `105:11` → VERIFIED；`90:8` → VERIFIED |
| math | `193:1` → NEEDS_REVIEW；`44:2` → VERIFIED | `184:3` → VERIFIED；`37:2` → VERIFIED |
| reasoning | `12:4` → VERIFIED；`25:1` → VERIFIED | `205:3` → VERIFIED；`65:3` → VERIFIED |
| writing/recommendation | `18:7` → NEEDS_REVIEW；`15:2` → VERIFIED | `5:20` → VERIFIED；`74:8` → VERIFIED |

## CRAG：跨领域干扰输入测试

CRAG 是问答与 RAG 事实性基准。它提供问题、参考答案和检索内容，但不提供 Career Vault 里的候选经历，也不提供 JD—经历相关性标签。此处仅把 10 个原始问题转成单条 requirement，对照项目中的虚构经历库运行 `EvidenceMatcher`。

结果为：10/10 未覆盖、0 条匹配、0 条 `ready_for_selection`。样本覆盖 finance、movie、sports 与 open 问题，其中 open 问题不保证与求职需求无关；所以这是小型的外领域输入冒烟测试，不是严格的负例金标准，也不能推导真实岗位匹配的误报率。没有运行 CRAG 官方 LLM-as-judge，没有生成 QA 答案，也没有使用 Perfect / Acceptable / Missing / Incorrect 标签。

CRAG 样本 ID：`3dbed55e-66a3-4dcd-907d-096f49387e41`、`55b219e5-ba31-4318-a73d-551f0fb9c546`、`6a9a6e0f-82fb-4302-806e-a49ef6b35a66`、`f8fc2c1a-4bcb-48be-857c-1b0dcf07034e`、`ecc1e84c-b979-4479-8275-eaa62020643f`、`1645bfaf-c829-43ba-ba37-096b7676258c`、`db078969-dcfd-4bd3-8d07-ee8ceceebafd`、`ce79ed8a-73cb-42ef-935b-121c13a9c61a`、`d535abd8-1361-4ad8-a82e-006ccdfc0cfb`、`1d2e8c37-296a-4309-83a2-e84d66dd4bb0`。

## 复现与完整项目测试

在 ApplyGuard 仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/evaluate_external_benchmark_pilot.py
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

脚本默认从 FELM 官方 Hugging Face 地址把归档读入内存，并读取相邻目录中本机已克隆的 CRAG 示例；可用 `--felm-zip`、`--crag-bz2` 指定本地文件。脚本不保存或输出原始数据文本。

完整项目测试：101 项运行，100 项通过，1 项 PaddleOCR 可选依赖测试跳过；测试命令退出码为 0。`git diff --check` 通过。

## 结论、风险与下一步

### 失效分析：为什么 7 条错误片段仍被 `VERIFIED`

这不是 7 条真实求职 Claim 的错误率，而是本轮合成适配暴露出的验证能力边界：

1. 适配器把 FELM 的生成片段直接设为 Vault 原始 Claim，并将 Claim、经历和证据源全部标为 `VERIFIED`、置信度设为 0.95；错误样本的纠错注释只作为证据描述文本。它没有把纠错注释转换成经过独立判定的结构化“矛盾”标签。
2. 当前 `ClaimValidator` 对原样未改写的 Vault Claim 主要信任上述验证状态及证据 ID 关联。它没有一般性的语义蕴含/矛盾判定器；较严格的新增事实检查主要在 Claim 文本被改写时运行。因此错误片段仍可通过结构检查。
3. 3 条错误样本进入 `NEEDS_REVIEW`，不能证明验证器正确识别了错误；检查逻辑可能只是对纠错注释中的否定表述触发了保守复核。剩余 7 条通过则说明这种词面检查覆盖不足。

因此，结果支持的结论是“当前验证链不能单靠已验证状态与 ID 关联证明 Claim 语义上受证据支持”，而不是“ApplyGuard 在真实简历中的错误率为 70%”。

### 可改进项与本轮边界

1. 对 C：把“来源是否可信/已核验”和“来源是否支持该 Claim”建模为不同判断；补充支持、矛盾、部分支持、无关及证据不足的人工标注测试。语义判断不确定时应进入 `NEEDS_REVIEW`，不能仅凭来源状态自动断言语义正确。FELM 样本可作为压力测试候选，但应保留其原始标签，并由独立人员复核映射，不能把纠错注释词面规则直接写进生产逻辑。
2. 对 B Matcher / SAG：CRAG 本轮没有 JD—经历正例和人工相关性标签，不适合据此调高匹配分数或声称准确率提升。应建立授权、脱敏并双人标注的职业材料集，在相同输入上比较原 Matcher 与 SAG 的 Evidence Recall@k、MRR/NDCG、误匹配率、覆盖率及延迟；只有正负例和分歧复核齐备后才调整排序策略。
3. 本次改版补充失效分析和复现材料；SAG 仍为默认关闭的辅助检索，本轮没有运行 SAG 对照实验。没有为降低 FELM 错误放行数而改动 Claim Validator、Career Vault CRUD 或原 Evidence Matcher，避免针对 20 个小样本过拟合。实际改进仍需在上述标注集上验证。
4. 使用 FELM 纠错注释做进一步规则前，仍须独立标注和人工复核，不能直接把数据集注释词面改写成生产规则。
5. 主要权衡：提高自动拦截可能增加误拦真实经历；放宽证据召回可能增加无关来源；调用语义模型或 SAG 会增加延迟、成本和数据处理边界。后续报告应同时呈现错误 Claim 放行、正确 Claim 误拦、人工复核率、Evidence Recall@k、延迟和费用，不能只报单一准确率。

代码改版保留队友的 CRUD、原 Evidence Matcher 和 Claim Validator 实现；SAG 只作为默认关闭的辅助检索适配，不改变核验状态。本评测报告和脚本可用于后续重复实验；结果不代表真实用户研究或统计显著结论。
