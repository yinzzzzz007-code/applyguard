# ApplyGuard 本地证据工作区技术设计

> 状态：设计稿，尚未实现。日期：2026-10-10。适用范围：课程项目在用户电脑上运行的 ApplyGuard。

## 1. 目标与边界

用户指定一个本地资料文件夹，ApplyGuard 从其中导入图片、PDF、Word 和 Markdown，提取可检索的内容。用户可以从 Career Vault 中的一项奖项或经历，查看它引用了哪份文件、文件的哪一页或哪一块原文，并检查简历表述是否超出了原件所能支持的范围。

本功能中的“证据锁定”指：一条表述绑定到**某个文件版本的具体位置**，文件变化后原关联被标为待复核；它不代表系统能够鉴定奖状真伪。OCR 只能读出图片上的字，不能证明颁发单位真实存在，也不能从“获奖”推断“精通某技能”。

已确认的需求：所有资料和识别处理留在本机；第一版支持图片、PDF、`.doc`、`.docx`、`.md`。工作区只处理用户明确选中的目录，不扫描整台电脑，不向云端视觉模型发送文件。

## 2. 现有程序与需要扩展的部分

当前 `backend/services/career_vault.py` 从 `data/career-vault.seed.json` 读取虚构经历，`evidence_sources` 已有 `evidence_id`、类型、描述和引用字段，Claim Validator 可以按证据编号检查关联。但它是只读演示数据：没有资料文件的导入、OCR、原件预览、文件版本记录和持久化的证据库。`frontend/src/pages/ClaimVerificationPage.tsx` 目前显示证据编号及描述，不能跳到原图或原文片段。奖项数据只有名称、颁发方、日期和描述，还没有与证据关联的字段。

`contracts/experience.schema.json` 设置了 `additionalProperties: false`。第一版应在**独立的本地证据表及关联表**保存文件、定位和审核记录，沿用现有 `evidence_id`；不要直接向冻结的 Experience 对象随意添加字段。若之后要让证据关联进入正式 API 契约，由 A/B/C/D 共同确定新版本契约。

## 3. 推荐架构

```text
用户选择本地目录
    ↓
前端枚举允许的文件并上传到 127.0.0.1 本地 API
    ↓
导入服务：检查类型/大小 → 保存只读原件副本 → SHA-256 → 去重/版本
    ↓
解析服务：图片 OCR；PDF/Word 提取文本，必要时逐页 OCR；MD 读取文本
    ↓
本地索引：文件、文本片段、页码/坐标、人工确认字段、关联关系
    ↓
Career Vault / Claim Review：搜索候选证据 → 人工核对 → 回看原件
```

浏览器页面必须由用户点击选择目录并授权。推荐用 `showDirectoryPicker()`，并为不支持它的浏览器准备目录上传或多文件选择的退路；后端不能从普通网页无授权地读取任意电脑路径。[MDN 文件夹选择文档](https://developer.mozilla.org/en-US/docs/Web/API/Window/showDirectoryPicker)。当前程序只面向本机时，服务继续绑定 `127.0.0.1`。浏览器传输的是所选文件内容和相对路径，后端在受控存储目录保存快照，不依赖浏览器暴露绝对路径。

第一版的元数据可用 SQLite 保存，原文件快照保存在 Git 忽略的本地目录。少量资料先用结构化字段和关键词检索；资料量增大时再为文字片段加 SQLite FTS5。向量检索可以后加，但无论采用哪种检索，都必须返回可定位的原件片段。[SQLite FTS5 文档](https://www.sqlite.org/fts5.html)。

这里的“Deep Research 式”操作限定在用户选定的**本地工作区**：将待核对的陈述拆成姓名、奖项、等级、时间等字段；分别检索文件；并列显示候选原文与冲突；最后给出带文件版本和定位的结论。多轮检索可以帮助找到被遗漏的材料，但不能把搜索摘要直接当证据，也不能越过人工核对。第一版先实现可定位的单轮检索，再考虑多轮检索。

## 4. 文件解析与定位

| 格式 | 本地处理方式 | 返回给界面的定位 |
| --- | --- | --- |
| JPG/PNG/WebP 等图片 | 本地 OCR，保存识别行、置信度和坐标；用户可纠错 | 原图上的矩形区域 |
| 文本型 PDF | 先提取原有文本；按块保留页码与坐标 | 页码、文字块和矩形区域 |
| 扫描型 PDF | 无可用文字的页面渲染成图片后 OCR | 页码、OCR 行和矩形区域 |
| `.doc` / `.docx` | 本地 LibreOffice 转为临时 PDF，保留原件；再按 PDF 流程解析 | 转换后 PDF 的页码与区域，同时标明“预览为转换件” |
| `.md` | 按文本读取，保留原始行号；不执行其中的 HTML/脚本 | 起止行号和原文 |

图片 OCR 可选 PaddleOCR 的**本地推理**能力；安装模型文件后要验证断网状态也能导入和识别。PDF 文本提取及页面坐标可使用 PyMuPDF，只有文字缺失或不可用时才逐页 OCR。Word 的 `.doc` 和 `.docx` 用本机 LibreOffice 转换，转换失败则显示可纠正的导入错误，不假装已经完成索引。[PaddleOCR 文档](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html)；[PyMuPDF 文本提取](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)与[OCR 说明](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html)；[LibreOffice 命令行转换](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)。

对于 Word 转换件，页码是转换结果的页码，可能与用户在其他软件中看到的分页不同。因此界面必须同时保留并提供原始 Word 文件，不把转换页码描述成原件的固定页码。

## 5. 数据模型：把“找到文件”和“支持陈述”分开

建议新增以下概念，字段名为设计建议，不是当前 API：

| 实体 | 关键字段 | 用途 |
| --- | --- | --- |
| `workspace` | `workspace_id`, `name`, `created_at` | 用户管理的一组本地资料 |
| `source_file` | `file_id`, `workspace_id`, `relative_path`, `media_type`, `size`, `sha256`, `imported_at`, `version`, `state` | 原文件快照与版本 |
| `source_span` | `span_id`, `file_id`, `page`, `bbox` 或 `line_start/end`, `raw_text`, `extractor`, `extractor_version` | 可回看的具体原文位置 |
| `evidence_record` | `evidence_id`, `span_ids`, `kind`, `normalized_fields`, `review_state`, `reviewed_at` | 人工确认后的证据条目 |
| `evidence_link` | `target_type`, `target_id`, `evidence_id`, `file_sha256`, `linked_at`, `link_state` | 奖项、经历、指标或 Claim 与证据的关系 |

`normalized_fields` 对奖状可包含获奖人、奖项名称、等级、颁发方、日期；OCR 原文与人工修改后的文字都要保留，不能用修正文本覆盖原始识别结果。`source_span` 必须定位到当前 `source_file` 的特定版本。SHA-256 用于检测是否为同一份文件内容，不用于判断文件真假。[Python `hashlib` 文档](https://docs.python.org/3/library/hashlib.html)。

例如，简历 Claim “获得校级程序设计竞赛二等奖”应能顺着 `claim_id → evidence_link → evidence_id → source_span → source_file` 回到奖状原图中“二等奖”所在区域。如果图片实际写“一等奖”之外的其他等级，或获奖人不同，状态应显示为冲突或待复核，而不是自动改写用户经历。

## 6. 交互与状态

1. **建立工作区**：用户选择文件夹；页面列出将导入的文件数、类型和不支持的文件。确认后才开始复制和索引。
2. **处理进度**：按文件显示“待处理、解析中、待人工核对、已核对、失败”。一份文件失败不应导致其余文件全部失败；失败项提供原因与重试。
3. **核对奖状**：左侧显示原图或 PDF 页，框出识别文字；右侧显示获奖人、奖项、等级、颁发方、日期及 OCR 原文。用户改正后点击确认，才生成可引用的证据条目。
4. **关联经历**：用户可手动选一个奖项或 Claim；系统搜索并推荐候选证据，同时展示具体原文。推荐只说明“可能相关”，由用户决定是否关联。
5. **回看来源**：在 Career Vault 和 Claim Review 点击证据编号，显示原件、定位、文件版本、核对者与核对时间。不存在或已失效的来源要显眼提示。
6. **修改与重新索引**：用户重新扫描或重新导入时，若文件哈希变化，创建新版本，旧版引用标为 `STALE`/待复核；不能把新文件默默替换到旧 Claim。第一版无需实时监听文件夹，因此只有重新扫描后才发现原件变化。复制简历内容前提示与最新证据版本是否一致。

显示状态建议分两层：**解析状态**（成功/失败/待纠错）和**证据审核状态**（未核对/已核对/冲突/已过期）。当前 Claim Review 的 `VERIFIED` 只表示相对本地资料可支持表述，不表示颁发机构或原件真实性经过外部认证。

## 7. 建议 API 与现有模块衔接

这些是新增接口的设计草案，并非当前已存在的接口：

| 接口 | 职责 |
| --- | --- |
| `POST /api/v1/evidence/workspaces` | 创建工作区元数据 |
| `POST /api/v1/evidence/workspaces/{id}/files` | 分批导入文件，返回每个文件的处理状态 |
| `GET /api/v1/evidence/files/{id}` | 获取文件元数据与解析状态 |
| `GET /api/v1/evidence/files/{id}/preview` | 经权限和路径检查后流式返回本地预览 |
| `GET /api/v1/evidence/search?q=...` | 返回候选证据及可定位的原文片段 |
| `POST /api/v1/evidence/{id}/review` | 提交人工修正及确认，记录审核时间 |
| `POST /api/v1/evidence/links` | 建立奖项/经历/Claim 与证据的关联 |
| `GET /api/v1/evidence/links?target_type=...&target_id=...` | 查看某一项目的证据链及版本状态 |

前端由 D 增加导入、核对和证据预览交互；经历库持久化及证据与 Claim 的关联需要与 B 的 Career Vault、C 的核验逻辑和 A 的 API/存储契约共同集成。现有证据编号可以作为关联入口，但 `awards` 目前没有 `evidence_ids`，第一版通过独立 `evidence_link` 表关联奖项。原有流程在证据未审核或过期时如何处理，应由核验规则决定并明确展示给用户。

## 8. 本地运行与安全要求

- 文件只发往本机服务；不调用云端 OCR、云端视觉模型或远程存储。安装阶段可下载软件与模型，实际识别须能在断网环境运行。
- 后端只读取用户导入的文件副本，不接受前端给出的任意绝对路径；预览接口用内部 `file_id` 定位，并验证文件确实属于本地工作区。限制扩展名、文件真实类型、大小、页数和批量数量。
- Word 转换使用受限的本地处理进程、独立临时目录和超时；不执行文档宏或外部链接。原件与转换件分开保存。
- 本地证据目录、索引数据库、OCR 结果及可能含个人信息的日志均不得提交到 Git。删除工作区时提示其引用的 Claim 会失去来源，并提供彻底删除本地副本的操作。
- 图片中可能包含姓名、学号、证书编号；界面展示时按需遮盖敏感字段，导出演示材料前使用虚构或获授权的数据。

## 9. 分阶段实施与验收

**阶段 1：本地导入与预览。** 支持图片、PDF、`.doc`、`.docx`、`.md`，生成文件快照、哈希和解析结果；能从每条结果回看原件。先用少量虚构文件完成端到端演示。

**阶段 2：人工核对与证据关联。** 奖状图片识别出至少获奖人、奖项、等级、颁发方、日期，允许纠错；确认后可关联一条奖项或 Claim；核验页能显示原文位置。

**阶段 3：版本与失效。** 修改、删除或重新导入源文件后，旧引用显示为待复核；重新确认后产生新版本关联。检查不一致奖项等级与姓名不会被错误标为已核对。

最小验收任务：用户把一张写有“程序设计竞赛二等奖”的奖状放进工作区，导入并核对，关联到 Career Vault 奖项，在 Claim Review 点击证据能打开原图并高亮“二等奖”；将简历表述改为“一等奖”时显示冲突；修改原文件并重新扫描后，旧关联提示过期。再分别用文本 PDF、扫描 PDF、`.doc`、`.docx` 和 `.md` 证明解析或明确报错，不静默漏掉文件。

## 10. 当前仍需团队决定的事项

1. 工作区数据由现有标准库 HTTP 服务扩展，还是由 A 决定迁到正式 API 框架；不影响上述数据边界。
2. `VERIFIED`、`NEEDS_REVIEW`、`BLOCKED` 与新引入的 `STALE` 如何映射，尤其是已过期证据是否禁止复制；需与 C 的核验规则对齐。
3. Career Vault 从只读 JSON 迁到可写存储的时间，以及是否发布新版 Experience 契约；需与 A/B 协调。
4. 演示时使用的虚构奖状、Word 和扫描 PDF 样本由谁提供，以及可否在仓库中公开；真实个人证件不应直接成为公开样例。

这些是实现时的接口和验收决策，不影响先制作本地导入、识别与原件定位的技术原型。
