# ApplyGuard

ApplyGuard 是一个在本机运行的求职准备工作台。把简历、项目材料和岗位 JD 放在一起，逐条检查经历表述，生成简历与面试准备资料。

当前更新分支为 `1118branch`。运行界面使用中文，支持从简历准备一路进入自我介绍和项目问答。

## 从简历到面试准备

1. **简历导入与经历库** — 导入文字 PDF，或选择本地 OCR 识别扫描件；核对并保存教育、项目、实习和技能。
2. **证明材料** — 导入项目 README、Markdown、PDF、Word 或图片，核对解析文字，再关联到相应经历。
3. **岗位说明与匹配** — 粘贴 JD，或从岗位雷达选择岗位，查看要求与现有经历的匹配情况。
4. **简历审查与陈述核验** — 批量生成表达建议，逐条预览与采用。事实拆分和核验说明使用中文，引文保留原文。
5. **申请内容检查与最终确认** — 查看拟填内容和风险，完成本地模拟确认，再进入简历生成。
6. **简历生成** — 提供中文学术技术、英文标准单栏和中文校招一页三种模板，支持删除预览内容、下载 TXT 和打印为 PDF。
7. **生成面经** — 从简历预览进入面经页，编辑 JD，生成 1 分钟、3 分钟自我介绍和模拟问答。

### 面经怎么生成

面经使用当前简历预览中的资料，预览里已删除的项目不会进入本次请求。通过侧栏直接打开时，可从当前经历库或本标签页暂存资料开始。

- 每个项目至少分配一道独立问题，并提供参考回答。
- 总题数至少 8 道；项目超过 8 个时，总题数相应增加。
- 问题覆盖岗位匹配、项目原理、技术选型、个人贡献、排查过程、指标验证和行为面试，页面标注对应项目。
- 两版自我介绍先展示，问答按题展开，支持下载整份 TXT。
- 缺少的实现细节标注为待补充，参考回答中的假设性分析与实际经历区分表述。
- 刷新可恢复本标签页的准备内容；JD 或资料变化后需要重新生成。

自我介绍时长按篇幅估计，应按个人语速试读。面经内容是模型生成的练习参考，使用前核对个人贡献、技术细节和数字。

## 1118branch 的主要更新

- 兼容 DeepSeek 的 JSON 输出，并在本机校验返回结构。
- DeepSeek 默认采用本机 MiniLM 向量检索，随后执行逐事实核验；可显式配置图谱扩展检索。
- Windows 后端启动时配置可写的 SAG 临时目录，启动脚本也同步设置。
- 润色提示词合并项目 README、JD 和原有 ASu 写作规范，支持解析成功的其他格式材料。
- 历史版本按条显示，核验页收起完整材料和逐事实依据，按需展开。
- 最终确认页增加简历生成入口，简历生成页增加面经入口。

## 安装和启动

本次开发使用 Windows、Python 3.12 和 Node.js 24。建议使用 Python 3.12 与 Node.js 24 LTS。

在仓库根目录打开 PowerShell，安装后端和 SAG 依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-sag.txt
Copy-Item .env.example .env
```

已有 `.env` 时直接编辑现有文件。填写服务地址、文本模型和密钥后，启动：

```bat
start-demo.bat
```

脚本启动后端和 Vite，并打开 [本机工作台](http://127.0.0.1:5173)。后端健康检查为 [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)。关闭服务可以运行 `stop-demo.bat`。

启动脚本会尝试安装缺少的 OCR 和前端依赖，并清理 8000、5173、5174 端口的占用进程。这些端口用于其他服务时，采用手动启动方式。

### DeepSeek 配置

在 `.env` 中设置下面各项，两个文本模型配置都需要填写：

```dotenv
APPLYGUARD_AI_BASE_URL=https://api.deepseek.com/v1
APPLYGUARD_AI_MODEL=deepseek-flash
APPLYGUARD_COMPLEX_AI_MODEL=deepseek-flash
APPLYGUARD_AI_API_KEY=填写自己的密钥
APPLYGUARD_GROUNDING_MODE=sag_atomic
APPLYGUARD_GROUNDING_STRATEGY=vector
```

实际模型名以账户可用服务为准。示例配置中的 Gemini 模型可按需继续使用。DeepSeek 聊天接口使用 JSON 对象模式，本机继续执行 JSON Schema 和原文引用检查。

DeepSeek 的 SAG 路径需要本地多语言 MiniLM。模型文件位于被 Git 忽略的 `data/local/models/multilingual-minilm/`；从 GitHub 克隆后需要另行准备。安装命令中的 `requirements-sag.txt` 包含 ONNX Runtime、NumPy 和 tokenizers。

从固定版本下载两个文件：

```powershell
$embeddingDir = Join-Path (Get-Location) 'data/local/models/multilingual-minilm'
New-Item -ItemType Directory -Path $embeddingDir -Force | Out-Null
$modelBase = 'https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/resolve/2c4055b12046f11709e9df2c122e59ffbdc2f900'
Invoke-WebRequest "$modelBase/onnx/model_quantized.onnx" -OutFile (Join-Path $embeddingDir 'model_quantized.onnx')
Invoke-WebRequest "$modelBase/tokenizer.json" -OutFile (Join-Path $embeddingDir 'tokenizer.json')
```

可通过 `APPLYGUARD_LOCAL_EMBEDDING_DIR` 指定已有模型的目录。实现使用 384 维向量和最多 128 token 的输入。下载来源及版本见 [MiniLM 模型文件](https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/tree/2c4055b12046f11709e9df2c122e59ffbdc2f900)。

其他模型网关默认使用 `full_expand` 和远端 `text-embedding-3-small`，需要服务支持相应的文本及向量接口。DeepSeek 下显式选择 `full_expand` 时也会调用图谱事实抽取，该路径对模型输出格式有额外要求。

### OCR 和文件格式

简历入口支持 PDF；图片型或扫描 PDF 选择“本地 OCR”，每次最多 5 页。

证明材料支持 Markdown、PDF、Word 和常见图片。Word 的 `.docx` 使用本地文本提取，旧版 `.doc` 需要安装 LibreOffice。图片和扫描件识别需要 PaddleOCR：

```powershell
.\.venv\Scripts\python.exe -m pip install paddlepaddle paddleocr
```

首次 OCR 可能下载模型。可通过 `APPLYGUARD_OCR_PACKAGES` 指定独立库目录，通过 `PADDLE_PDX_CACHE_HOME` 指定 OCR 模型缓存。识别结果应逐项核对。

### 手动启动

后端：

```powershell
.\.venv\Scripts\python.exe -m backend.app
```

另开终端启动前端：

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

前端构建产物可以通过 `npm run build` 生成。后端支持直接访问已登记的页面，包括 `/interview`。

## 材料、核验和数据

生成建议会处理当前草稿中符合范围的项目、实习和奖项条目。选择某一条时，右侧显示该条建议。个人和教育资料按表单使用。

原件提供事实，JD 决定表达重点。README 可以解释项目功能与技术选择，个人贡献仍需要对应材料。生成建议后由用户逐条采用，编辑或恢复历史会使旧核验失效。严格导出要求当次原子核验通过；个人确认稿导出会保留材料状态记录。

本地文件解析、OCR 和 DeepSeek 的向量计算在本机执行。模型生成建议、事实核验与面经时，相关正文会发送到配置的服务；页面提供相应确认提示，调用可能产生费用。面经请求选择姓名、教育、技能、简介及项目和实习字段，正文中的个人信息仍应自行检查。

`.env`、`data/local/`、`output/` 已被 Git 忽略。个人草稿、材料快照、模型缓存与运行日志存放在这些本地目录；部分编辑记录和面经使用浏览器存储。清理浏览器数据可能丢失暂存记录。

材料核验表示所提供材料对陈述的支持情况。模拟申请流程由用户检查和确认，真实投递由用户在招聘网站完成。

## 检查与验证

后端全量回归会写入带日期的本机报告：

```powershell
.\.venv\Scripts\python.exe scripts/run_test_report.py --label 1118branch --all
```

单独检查面经接口：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_interview_guide
```

前端在 `frontend/` 中运行：

```powershell
npm run build
npm run lint
npm run smoke
```

单元测试使用模型桩与虚构资料。真实服务测试另外运行并产生费用。本次已用虚构材料验证 DeepSeek 的检索核验、中文事实说明、两版自我介绍以及三个项目逐一出题，也检查了桌面／手机界面、下载和刷新恢复。测试结果反映对应样本和环境，模型建议仍需本人核对。

Windows 无符号链接权限时，相关回归会跳过。真实招聘投递、独立真人盲评及生产级并发仍未覆盖。

2026-11-18 的发布检查在不含私人草稿和密钥的源码副本中完成。
后端 394 个测试方法中 392 通过、2 个符号链接测试跳过，参数子用例 711 个；
前端 44 项 smoke 测试通过，构建通过，lint 为 0 错误、10 条警告。
原始本机报告保存在被 Git 忽略的 `output/` 中。测试方法与参数子用例分别计数。

## 代码与历史资料

| 目录 | 内容 |
| --- | --- |
| `backend/services/` | 证据解析、SAG 检索、原子核验、润色与面经生成 |
| `frontend/src/pages/` | 工作台页面与简历、面经界面 |
| `contracts/` | 模块 JSON Schema 契约 |
| `tests/`、`frontend/scripts/` | 后端回归、接口和前端状态测试 |
| `data/evidence-samples/` | 公开虚构样例 |
| `docs/` | 设计、实验、测试与交接记录 |

- [架构与代码地图（2026-11-13）](docs/architecture-2026-11-13.md)
- [Harness 授权、安装与证据回传](docs/agent-connector.md)
- [README 写作规范与第三方引用](THIRD_PARTY_NOTICES.md)
- [申请内容检查与简历生成交接](docs/resume-ats-handoff-2026-11-11.md)
- [Gemini 测试与严格导出记录](docs/testing-report-2026-11-13-gemini.md)
- [职责、环境歧义与 OCR 复测](docs/testing-report-2026-11-13-ambiguity-repair.md)
- [SAG 实验与验证范围](docs/sag-v2-results.md)
- [历史版本贡献与署名](docs/contribution-attribution.md)

此前由姜凌天（Gitvextor）组织的 SAG、原子核验、错改保护与相关实验记录继续保存在 `docs/`。ASu、SAG、DocLens、RefChecker 等复用方法、源码版本和许可信息见第三方说明及相应目录。
