# 指定 GitHub 分支与 Gemini 复测（2026-11-13）

**最新结论：OCR 已安装至 E 盘，后端 328 项全部通过、0 跳过；严格导出、本机 Harness 真实连接和首页视频均通过相应验证。** 前端 39 项通过，构建通过，lint 0 错误／4 项原有警告。此前导出连续两次 503 的失败记录保留；11:51 的新请求重新核验为 VERIFIED，在 40.82 秒内返回 HTTP 200 和正文。详见文末续测。

这是虚构材料的小规模功能检查，不是独立模型准确率评估。新增浏览器测试覆盖首页和 Harness 入口；严格导出通过真实 HTTP 验证，未覆盖整份用户简历的浏览器全流程。原子核验通过只表示材料内容支持陈述，不能鉴定材料真伪。

## 基线、环境与修改

- 仓库：[yinzzzzz007-code/applyguard](https://github.com/yinzzzzz007-code/applyguard)。分支：`feature/ui-review-improvements-20261105`。
- 使用 `git ls-remote` 核对远端后重新克隆，基线：[1eab77cbcd86d79a180ce2834ab3a82a777df89f](https://github.com/yinzzzzz007-code/applyguard/commit/1eab77cbcd86d79a180ce2834ab3a82a777df89f)，提交时间 2026-11-10 11:07 +08:00。
- 本次目录：`D:\jianglingtian\SynologyDrive\软件工程大作业\applyguard-gemini-20261113`。未用外层旧检出的代码替代该基线。
- Windows、Python 3.13.11，使用外层工作区现有 `.venv`；按 `requirements-sag.txt` 补齐依赖，新增安装 pdfplumber 0.11.10、pdfminer.six 20260107、pypdfium2 5.15.2。前端重新执行 `npm ci`。
- 原仓库文本模型默认已经是 `gemini-3.1-flash-lite-preview`，无需替换业务代码。新建本机 `.env`，统一普通、复杂、高风险二次判断为该模型，地址为 `https://api.chatanywhere.tech/v1`。embedding 保留 `text-embedding-3-small`／1536 维。
- `.env` 不含密钥且被 Git 忽略。真实调用用隐藏输入，密钥仅在进程内使用；测试仅发送仓库自带的虚构案例。
- 首轮代码修改为 `tests/test_wording_review.py` 的测试隔离，共 6 行：屏蔽本机可选高风险模型配置，并阻止措辞单元测试意外构造真实 HTTP 客户端。后续按用户要求修复连接流程和首页，见文末；未修改生产核验规则或关闭高风险复核。
- 新增本测试报告及 [当前架构与代码地图](architecture-2026-11-13.md)。

## 首轮工程回归证据

| 范围 | 命令 | 结果 |
| --- | --- | --- |
| 原始 GitHub 基线后端 | `python scripts/run_test_report.py --label github-1eab77c-full --all` | 321 方法：320 通过、1 跳过；686 参数子用例；18.13 秒 |
| 启用统一模型配置后 | `python scripts/run_test_report.py --label gemini-config-final --all` | 319 通过、1 失败、1 跳过；失败为单元测试继承了可选真实模型配置 |
| 修复测试隔离后 | `python scripts/run_test_report.py --label gemini-config-isolated-final --all` | 320 通过、1 跳过；686 参数子用例；16.93 秒 |
| 前端构建 | `npm run build` | 通过；TypeScript 与 Vite 构建，6.70 秒 |
| 前端静态检查 | `npm run lint` | 通过退出码；0 错误、4 警告，2.40 秒 |
| 前端状态测试 | `npm run smoke` | mock gate smoke 成功，36 项 Node 测试通过；3.65 秒 |

测试方法数量与参数子用例分开记录，不相加作为“独立测试总数”。唯一跳过是 `test_ocr_embedded_image_when_no_text_layer`，原因是未安装可选 PaddleOCR。

lint 警告未修改：`jdMatchScope.ts:12` 多余转义，`DemoContext.tsx:422` Fast Refresh 导出约束，`CareerVaultPage.tsx:528` 渲染期间访问 ref，`CareerVaultPage.tsx:593` effect 同步 setState。

首次受限运行在本机回环／MCP 测试阶段长时间无结果，已中断，不计为通过；允许测试所需回环连接后完成全量测试。完整记录：

- [基线后端报告](../output/test-reports/20261113_111117_941127_github-1eab77c-full/report.md)
- [配置触发的失败记录](../output/test-reports/20261113_112028_523818_gemini-config-final/report.md)
- [最终后端报告](../output/test-reports/20261113_112152_611357_gemini-config-isolated-final/report.md)
- [前端构建](../output/test-reports/20261113_110719_002619_github-frontend-build/report.md)、[lint](../output/test-reports/20261113_110719_021902_github-frontend-lint/report.md)、[smoke](../output/test-reports/20261113_110719_024878_github-frontend-smoke/report.md)

每份自动报告同目录保留 `report.json`、`test.log` 和源文件 SHA256。以上 `output/` 链接是本机证据，目录被 Git 忽略，尚未发布为 GitHub 附件。

## 真实服务与完整流程

服务预检：文本 JSON 调用 1.54 秒，实际响应模型名为 `gemini-3.1-flash-lite-preview`；embedding 调用 1.10 秒，返回 `text-embedding-3-small`／1536 维。详见 [连通性记录](../output/model-connection.json)。这只证明调用成功，不证明复杂核验稳定。

首先执行原仓库 `scripts/live_grounding_pilot.py`。SAG 为每条陈述找到 1–2 份原件，但 good、bad 两轮均出现“核验未完成”，10 条全部 `NEEDS_REVIEW`；不能把 0 条错误放行解释为正确分类。仅检索润色预览一轮正常结束，仍为需复核，符合预览模式的设计。

首次 good／bad／预览用时分别为 141.29／55.41／29.31 秒。原始结果保留在 [integration-live-initial.json](../output/integration-live-initial.json)。这份脚本为了比较模式会把服务器最低模式设为 off，因此不能单靠它证明默认禁止降级的行为。

随后复用原件，对结构化模型调用单独诊断，捕获一次 HTTP 503；现有重试后，5 条支持句全部 `SUPPORTED` 且完整性检查通过。SDK 等价判断也成功。详见 [调用轨迹](../output/model-structured-trace.json)、[核验结果](../output/model-structured-result.json)、[SDK 结果](../output/model-wording-sdk.json)。首次工作流没有保留底层错误码，因此不能断言其每一次失败都由 503 引起。

最后在服务器默认 `sag_atomic` 下运行实际 HTTP 复测，继续使用相同五组虚构材料与已建好的来源缓存，生产代码未替换模型或检索器。所有文本模型仍为 Gemini，结果如下：

| 步骤 | 预期 | 实际 | 耗时 |
| --- | --- | --- | ---: |
| 5 条支持句重新核验 | 全部通过 | 5/5 VERIFIED，无 grounding.error | 76.33 秒 |
| 5 条错误句重新核验 | 全部阻断 | 5/5 BLOCKED；期间一次 503 后重试恢复 | 59.60 秒 |
| 1 条原子模式润色 | 最终文字有依据、等价 | 成功修复后采用，VERIFIED | 112.37 秒 |
| 1 条已核验稿导出 | 导出前再次核验成功 | 失败：两次模型 HTTP 503，应用返回 HTTP 422，未导出 | 8.85 秒 |

五组场景覆盖跨项目技术错配、职责／贡献归属、被更正的旧稿、计划与完成状态、指标和测试范围。样本作者提供标签，且已用于既有开发／诊断，不能据此报告总体错误率或泛化准确率。

润色例子：原句为 `Alex contributed Python API testing to Atlas.`；模型最初改成 `Developed Python API tests for the Atlas project under the direction of the project lead.`，增加了原句未表达的监督关系。等价判断识别变化，单次修复为 `Alex contributed Python API testing to the Atlas project.`，重新核验后采用。此例确实运行了修复链；未触发可选高风险二次判断，不能算该分支的真实服务效果验证。

完整结果见 [atomic-live-retest.json](../output/atomic-live-retest.json)，其中 `passed=false`，不能只看脚本退出码。复测入口为 [check_atomic_workflow.py](../output/check_atomic_workflow.py)，诊断入口为 [check_structured_model.py](../output/check_structured_model.py)。它们是本次临时测试工具，位于被忽略的 `output/`，不改变业务行为。

## 已发现问题与边界

1. **网关可用性影响最终导出。** 普通短请求能成功，复杂工作流仍多次遇到 HTTP 503。重试有时恢复，但连续失败时导出被阻止。当前不应宣称真实完整流程稳定通过，也没有通过关闭复核来绕过失败。
2. **措辞测试依赖本机配置，已修复。** 设置 `APPLYGUARD_STRONG_AI_MODEL` 后，一个只注入主模型桩的测试会额外尝试真实二次判断，导致无密钥时失败。现在在测试类统一隔离该选项，禁止构造真实客户端；专门的高风险路由测试仍保留。
3. **静态路由登记差异，续修已完成。** 前端有 `/help` 而后端未登记；本轮补齐并新增直接 HTTP 访问测试。
4. **未验证项目。** 真实 PaddleOCR、LibreOffice 转换环境、独立外部 Radar 服务、系统剪贴板、真实招聘投递、真人盲评及生产级并发／隔离。首页和 Harness 浏览器交互已在续测补充；Node smoke 与浏览器测试分别报告。

严格导出已在下列续测完成；若要评价减少幻觉的效果，应冻结实现后另取独立标注样本，分别报告错改产生、修复、误拦、漏放、需复核、延时和费用。本次没有测量整个 SAG／SDK 流程的总账单，不能推算总费用。

## 连接修复、首页视频与严格导出续测

2026-11-13 11:49 再次 `git ls-remote` 核对指定分支，远端仍为 `1eab77c`。下面均是在该提交基础上的修改。使用的真实模型仍为 Gemini 3.1 Flash Lite／ChatAnywhere；Harness 使用本机已安装 0.2.1-rc.3。

**连接故障修复。** Vite 原来重写 Host 为后端 8000，而浏览器 Origin 为前端 5173，同源保护拒绝 UI 请求。保留原 Host 解决代理问题，未放松跨站限制。同时移除 Python／脚本路径占位符，增加只读环境检测、安装指南、独立 Harness 启动器和自动轮询。预检成功不会误报配对；隔离本地授权禁止用云端快捷启动。

**首页视频修复。** 将帮助页内的 24 秒引导置于首页首屏，默认展开，保留静音／播放／暂停／章节和减少动态效果。中等宽度保持横屏，手机竖屏。首轮浏览器测试发现 StrictMode 清理与异步初始化冲突，以及离开视口后画面被卸载；现在跳过已取消的初始化，离开视口只暂停，离开页面才清理画布。加入 `/help` 后端直达。

| 检查 | 实际结果 | 原始证据 |
| --- | --- | --- |
| 最终后端回归 | 328 方法，327 通过、1 OCR 跳过；686 子用例；17.79 秒 | [report.json](../output/test-reports/20261113_115653_325811_harness-home-final/report.json) |
| 前端状态回归 | 39 项全部通过 | [smoke](../output/test-reports/20261113_115445_888293_harness-home-smoke/report.json) |
| 最终前端构建 | 类型检查和 Vite 构建通过；3.61 秒；保留已有大 chunk 提示 | [build](../output/test-reports/20261113_120117_196135_harness-home-delivery-build/report.json) |
| 最终前端静态检查 | 0 错误，4 项原有警告 | [lint](../output/test-reports/20261113_120117_339309_harness-home-delivery-lint/test.log) |
| 本机 Harness 真实探针 | 17.482 秒；已配对；检索 4 条／提交 3 条；退出 0 | [report.json](../output/test-reports/20261113_114000_harness-live/report.json) |
| Harness 浏览器完整入口 | 两次真实运行通过；最终 15 项检查通过，真实启动器和 Gemini 回传；无页面异常 | [最终 report.json](../output/test-reports/2026-11-13T04-03-30-322Z_agent-browser/report.json)、[首轮通过记录](../output/test-reports/2026-11-13T03-50-23-369Z_agent-browser/report.json) |
| 首页视频真实浏览器 | 首次播放、默认静音、暂停／重播／章节、导入／帮助、1280／手机宽度、减少动态效果通过；无页面及控制台异常 | [report.json](../output/test-reports/2026-11-13T03-57-57-822Z_home-browser/report.json) |
| 严格导出真实续测 | 首次重试即 HTTP 200；40.82 秒；重新核验 VERIFIED；SHA256 与正文一致；模型错误 0 | [report.json](../output/test-reports/20261113_115124_strict-export-retry/report.json) |

导出正文为 `Alex contributed Python API testing to Atlas.`。请求显式 `export_policy=verified`、`human_confirmed=true`，服务端重新运行原子核验，沿用原件检索缓存但未复用旧通过状态。此前失败报告不修改。该结果证明本次同一小样本导出可用，不证明网关长期稳定。

Harness 浏览器测试还覆盖同源保护、未选择外发规则时禁止授权、等待与配对区分、撤销期间忽略旧响应、撤销令牌失效和离页撤权。缺依赖界面通过响应夹具模拟；真实环境已安装，截图名称明确标记 simulated。所有文件是测试生成的虚构 Atlas 材料，没有读取用户真实材料。

**截图与复现。** [首页首屏](../output/test-reports/2026-11-13T03-57-57-822Z_home-browser/homepage-hero.png)、[手机首页](../output/test-reports/2026-11-13T03-57-57-822Z_home-browser/homepage-mobile.png)、[安装指引](../output/test-reports/2026-11-13T03-50-23-369Z_agent-browser/harness-installation.png)、[实际配对及证据回传](../output/test-reports/2026-11-13T03-50-23-369Z_agent-browser/harness-connected.png)。入口为 `scripts/home_browser_smoke.cjs`、`scripts/agent_browser_smoke.cjs`、`scripts/harness_agent_probe.py`；安装和环境变量见 [连接文档](agent-connector.md)。严格导出本次入口为被忽略的 `output/retry_strict_export.py`。

首次连接浏览器测试因精确 label 选择器误含 textarea 初始内容失败，调整选择器后通过。首页各次失败与截图保留于 `output/test-reports/*_home-browser`，没有以成功记录覆盖。Playwright 安装遇到本机证书信任问题后采用 Node 系统证书，未关闭 TLS 校验。启动器默认启用系统证书；12:03 清除外层证书环境变量后再次实际连接成功，用户无需手动补设。首页曾排查软件渲染，但最终用默认 Edge 参数通过，不依赖额外 GPU 标志。

## 14:43 OCR 安装与续测

在 `E:\ApplyGuard\ocr\packages` 安装 PaddleOCR 3.7.0、PaddlePaddle 3.3.1（CPU）及其依赖，pip 缓存、安装临时文件与中文模型也位于 `E:\ApplyGuard\ocr`；现有 Python 仍在 D 盘。项目未跟踪的 `.env` 通过 `APPLYGUARD_OCR_PACKAGES` 指向库目录，`PADDLE_PDX_CACHE_HOME` 指向 E 盘模型目录，并将相关模型下载缓存指向 E 盘；未修改系统全局 Python。

原来跳过的 DOCX 内嵌中文图片测试实际通过，1 项通过、0 跳过（首次下载模型及测试 68.76 秒）：[单项报告](../output/test-reports/20261113_144332_970124_paddleocr-e-target/report.json)。测试是合成清晰图片，不代表低清晰度扫描件的总体准确率。测试也已收窄跳过条件：初始化或执行失败不会只因错误文字包含 paddle 而误判为跳过。

第一次完整回归将所有临时文件设在 E 盘，因 E 盘为 exFAT、不支持测试要求的符号链接，产生 3 个夹具错误和 1 个跳过：[失败记录](../output/test-reports/20261113_144506_566404_paddleocr-e-full/report.json)。将测试临时目录设为 D 盘项目的 `output/test-tmp` 后，全量 **328 通过、0 失败、0 跳过、686 参数子用例**：[最终报告](../output/test-reports/20261113_144630_068694_paddleocr-d-temp-full/report.json)。库、缓存和 OCR 模型仍在 E 盘；测试临时目录是工作区自己的临时文件，不占 C 盘。
