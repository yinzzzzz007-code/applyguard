# ASu原版复用与岗位雷达许可核实

日期：2026-10-30（北京时间）。本轮只更新本地实验版，未推送GitHub。入口仍为“简历审查 → 有依据的润色 → 生成润色建议”。

## 上游版本与许可

| 项目 | API核实的main提交 | 最后提交时间（北京时间） | 处理 |
| --- | --- | --- | --- |
| Hisn00w/ASu-skills | `d27fd2a3864c48472a5c8ed942410098ba9cd35f` | 2026-10-28 09:14:31 | MIT；原样复用选定文件，保留许可与作者 |
| Haoyu-Gu/ai-career-radar | `0ca459b3f6975d93a08cc5eea7adfca7e2a89b5c` | 2026-09-28 12:03:17 | 完整文件树无许可证；README、pyproject及前端package.json也未见授权声明；保留既有API互操作 |

核对了GitHub API提交及完整未截断文件树，并读取原件。公开仓库不自动授予源码并入、修改和再分发许可；雷达源码合并需要作者授权或补充合适许可证。[GitHub许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)。本轮未联系作者，也未将雷达源码复制到项目。

## 原样复用的范围

`third_party/asu-skills/`保留以下6个原文件，下载时对照GitHub树中的Git blob SHA1验证，另记录SHA256，共26,773字节：

- `LICENSE`，Copyright (c) 2026 Hisn00w，MIT；
- `skills/great-resume/SKILL.md`；
- `skills/great-resume/references/claim-evidence-ledger.md`；
- `skills/great-resume/references/business-analysis-evidence.md`；
- `assets/career-claim-ledger-template.json`；
- `scripts/validate_claim_ledger.py`。

来源固定为[上游提交](https://github.com/Hisn00w/ASu-skills/tree/d27fd2a3864c48472a5c8ed942410098ba9cd35f)，[许可原文](../third_party/asu-skills/LICENSE)随副本保留；[UPSTREAM.json](../third_party/asu-skills/UPSTREAM.json)记录全部指纹。`.gitattributes`保护上游原始换行，原文件没有添加Gitvextor署名或修改文字。Gitvextor署名只在本地适配代码中。

`great-resume`的核心是Skill指令与证据组织规范，不能描述成一个完整的React页面或可单独调用的简历改写算法服务。本次把这些原版规范真正加入现有模型润色请求，适配层在`backend/services/asu_resume.py`，调用链为：

`/api/v1/resume/polish → GroundingService → AtomicVerifier.polish → ASu原版规范 → 模型建议 → 原子事实/信息保留核验 → 人工采用与历史记录`。

基本润色加载原版Skill及主张—证据账本；材料或岗位涉及SQL、商业分析、成本测算等时再加载商业分析规范，减少不相关提示词。上游文件完整保留，加载的每份原文保持完整；适配指令另外约束只输出请求的经历改写，不生成HR消息、不执行脚本或连接额外工具。

建议仍受来源归属、原文保留、数字单位、人工确认及历史回滚约束。ASu账本里的“已确认”不直接变成ApplyGuard的VERIFIED。上游文件缺失、内容变更或许可/版本校验失败时，保留原稿并待复核，不静默退回一个冒充ASu的实现。

账本模板和原版Python校验器作为配套工具原样保留，已运行原版校验器检查原版模板。该工具仅做结构/状态校验，未替换本应用的事实判断器。HR开场白、岗位定位的多版本输出、HTML/PDF简历制作、自动投递等整套ASu功能不在本次接入范围；未安装全局Skill或修改Harness配置。

## 岗位雷达继续怎样使用

目前ApplyGuard已有本地岗位收藏、完整JD导入、版本保存和雷达API适配；配置本机独立雷达后可读`GET /api/jobs`与`GET /api/jobs/{id}`。我们写的适配代码不等于原仓库的采集器/看板已经搬入。启动、配置和边界见[岗位雷达连接指南](career-radar-integration.md)。

取得适当授权后，可以再原样引入官方岗位采集器、去重/扫描状态保护、筛选和抓取进度；应继续区分招聘要求与候选人实际经历。当前没有因为用户点击润色而自动爬取招聘网站或启动用户Agent。

## 已执行验证

| 时间（2026-10-30，北京时间） | 范围 | 结果 |
| --- | --- | --- |
| 16:07:21–16:07:24 | ASu集成及事实保护相关回归 | 42/42方法通过；12参数子用例另计 |
| 16:07:25 | 上游原版账本校验器+原版模板 | 退出码0，通过 |
| 16:10:16–16:10:29 | 全部后端回归 | 237方法：236通过、0失败、1可选OCR跳过；295参数子用例另计 |
| 16:17:18–16:17:31 | 加入语言保持修复后的全部后端回归 | 239方法：238通过、0失败、1可选OCR跳过；299参数子用例另计 |
| 16:23:38–16:23:39 | 最终来源指纹定向回归，沙箱运行 | 7通过、2环境错误：Windows沙箱拒绝访问临时目录；原始失败报告保留 |
| 16:24:07 | 相同9项定向回归，正常本地临时目录 | 9/9通过；10参数子用例另计；未改变测试断言 |

覆盖6原文件的逐字节一致性、真实调用链中包含原版规范、按需商业分析规范、无依据建议仍被拒绝、缺文件保留原文、篡改文件停止、仅核验时不加载写作Skill，以及既有授权/撤权/回滚/数字单位/岗位雷达逻辑。工程桩测试不证明真实模型效果提升。

逐次日志位于`output/test-reports/20261030_160721_379365_asu-original-integration`、`20261030_160725_008833_asu-upstream-ledger-validator`与`20261030_161016_024914_asu-full-regression`。真实模型小样本另列，不能拿之前冻结实验的257条有效配对成绩当作ASu接入后的成绩。

修复后全量报告：`output/test-reports/20261030_161718_412150_asu-language-fix/report.md`。最终来源指纹检查的失败与重试分别为`20261030_162338_986931_asu-final-provenance`和`20261030_162407_565559_asu-final-provenance-retry`；同目录保留JSON及完整日志。全部时间为2026-10-30北京时间。

收尾检查（2026-10-30）：重启本轮实验服务后，`http://127.0.0.1:8897/health`与`/resume`均返回HTTP 200；`git diff --check`通过。对38个本地修改/新增的代码及文档文件扫描长`sk-`凭据模式，未发现命中；这属于有限模式检查，不等同于完整秘密检测。模型密钥通过隐藏输入只保留在服务进程内，未写入源码。没有重跑付费模型批次，也没有推送远端。

## 真实模型试跑与发现后修复

16:11:47–16:13:23，ChatAnywhere `gpt-4.1-mini`，3条虚构经历，6次调用，14,868 token（输入12,011，输出2,857），95.984秒。原始报告：`output/test-reports/20261030_161147_186546_asu-live-3/report.json`。固定AllSources夹具提供原文，只测试写作与核验链路，不包含SAG引擎检索或Harness，不发送用户真实材料。

| 虚构案例 | 实际建议行为 | 当次结果及处理 |
| --- | --- | --- |
| Atlas接口测试 | 把英文改成中文，保留离线和未部署的主要信息 | 当次事实核验放行，但违反保持原稿语言的输出约束；随后新增中英语言变化拦截及每条草稿语言提示，回归确认即使事实判断为支持也不采用擅自翻译 |
| 枫叶SQL测算 | 遗漏“尚未实施”，把项目负责人改写为负责实施 | 信息保留检查拒绝，恢复原文及其核验结果 |
| 拼图准确率 | 保留80%→84%，省略显式“提高4个百分点” | 信息保留检查保守拒绝，恢复原文；这也暴露对可推算等价信息可能过度拦截，不能算作已证明的错误修改检出 |

这一轮没有证明原版ASu优于旧提示词，也没有“零幻觉”结论。原版规范改善的是输入给模型的写作流程，最终行为仍依赖模型和上下文。语言修复只针对可明确识别的中英文切换，短句/混合语言不武断归类。修复后保留原样ASu文件；适配规则及其SHA256单独记录。没有为补一个修复反复重跑付费批次。
