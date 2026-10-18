# ApplyGuard

ApplyGuard 是在本机运行的求职申请辅助原型：整理个人经历与证明材料，对照岗位要求查看相关证据，审查简历陈述，再通过模拟网申页面由用户人工确认和复制填写稿。

`v1.0.0` 分支保存课程项目的当前可运行版本。它不是自动投递工具；模拟 ATS 不会连接真实招聘网站，也不会替用户提交申请。

## 当前功能

| 页面 / 模块 | 当前实现 |
| --- | --- |
| 简历识别、Career Vault | 导入 PDF 简历并编辑本机草稿；演示经历数据仍以虚构 JSON 为基线 |
| 本地证据工作区 | 用户选择文件或文件夹，导入图片、PDF、`.doc`、`.docx`、Markdown；保存本机文件快照、哈希与来源位置，核对奖项字段并关联经历 |
| JD Input | 岗位文本可走离线规则解析；配置 API Key 后可选择模型解析，失败时显示回退状态 |
| Evidence Match / Resume Review | 查看要求与经历的匹配结果，审查拟使用的简历内容 |
| Claim Verification | 查看证据编号、原件来源和核验状态；有冲突或过期的材料提示复核 |
| ATS Simulator / Human Confirmation | 固定映射的本地模拟表单；用户检查并手动复制内容，最终投递由用户本人完成 |
| Application History | 浏览器内保存模拟记录摘要；不代表真实投递记录 |

证据工作区的 OCR、文本检索和关联只能说明“本地文件中的内容是否支持这句话”，不能鉴定证件真伪。`data/evidence-samples/` 是公开的**虚构样例**；图片样例配有模拟 OCR 结果，不能作为真实 OCR 准确率的证明。

可选的 [SAG 辅助检索](docs/sag-auxiliary.md) 能对本机 SAG 已索引的证据原文做按信源检索，并把命中的原文块映射到既有 Evidence ID。默认关闭；不会替代当前匹配算法、证据核验或人工确认，也尚未证明能提升准确率。

## 快速运行（Windows）

需要 Python 3.11+、Node.js 20.19+ 或 22.12+，以及 npm。下载仓库后在仓库根目录执行：

```bat
start-demo.bat
```

脚本会准备缺少的依赖，启动本机后端和前端，并打开页面。默认地址为 `http://127.0.0.1:5173`，后端健康检查为 `http://127.0.0.1:8000/health`。脚本会清理占用 8000、5173、5174 端口的旧进程；如这些端口用于别的程序，请改用下面的手动启动方式。结束演示可运行 `stop-demo.bat`。

手动启动时，分别开两个终端，并先进入仓库根目录：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m backend.app
```

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

前端通过 Vite 代理访问本机后端。离线演示无需 API Key。首次进入可从“简历识别 → 经历库 → 本地证据工作区 → 岗位说明”开始；证据工作区可导入 `data/evidence-samples/` 演示材料。

## 本地证据工作区

1. 在“本地证据工作区”选择一个文件夹，或单独添加文件。页面会列出待导入内容，隐藏目录和不支持的类型不会进入索引。
2. 导入后查看原件、解析文字和建议字段。图片或扫描 PDF 的真正 OCR 需要额外安装本地 PaddleOCR；没有 OCR 时会提示无法识别，仍可检查原件。样例图片的 `.ocr.json` 是明确标注的演示旁路。
3. 核对获奖人、奖项、等级、颁发单位、日期等字段，再手动关联到一条经历或奖项。核对文件与确认关联是两次独立操作。
4. 如果重新导入的同路径文件内容发生变化，系统保留文件版本并提示旧关联待复核。点击证据可回看相应原件；关联或 OCR 结果不能证明原件真实性。

`.docx` 的文字提取依赖 `python-docx`。旧版 `.doc` 需要本机安装 LibreOffice；扫描 PDF 和图片识别需要本地 OCR 模型。默认依赖只含可直接安装的基础组件，缺少可选工具时界面应给出明确提示。单个文件建议不超过页面显示的 6 MB 限额。

详细数据模型与边界见 [本地证据工作区技术设计](docs/evidence-workspace-design-zh.md)。

## 配置与资料保护

默认使用离线规则解析岗位。若要测试模型解析，可把 `.env.example` 复制为 `.env`，在本机填写 `APPLYGUARD_AI_API_KEY` 等配置，并在页面选择模型解析。`.env` 会由后端读取且被 Git 忽略；不要把真实 Key 写进源码、文档或截图。**证据文件解析始终按本地处理设计**，岗位模型解析是独立的可选功能。

本机简历草稿、导入的原件快照、OCR 结果和 SQLite 索引默认位于 `data/local/`，已被 Git 忽略。可通过 `APPLYGUARD_LOCAL_DIR` / `APPLYGUARD_EVIDENCE_DIR` 将它们放到仓库外的私人目录。GitHub 只应接收源码、文档及明确标记为虚构的样例；推送前请检查自己新增的文件与提交差异。

## 验证

在仓库根目录运行后端测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

在 `frontend/` 运行前端检查：

```powershell
npm run build
npm run lint
npm run smoke
```

以上命令默认不调用付费模型。模型质量评测需要单独配置 Key；不要把测试生成的个人资料或本机数据库提交到仓库。

## 项目结构

| 路径 | 内容 |
| --- | --- |
| `backend/` | 本机 HTTP API、岗位解析、证据工作区与核验服务 |
| `frontend/` | React + Vite 界面、模拟 ATS、人工确认与本地申请历史 |
| `contracts/` | 模块之间的 JSON Schema 契约 |
| `data/evidence-samples/` | 可公开的虚构证据样本及生成说明 |
| `data/local/` | 被 Git 忽略的个人草稿、导入文件与索引 |
| `tests/` | 后端和接口测试 |
| `docs/` | 系统架构、接口与研究文档 |
| `presentation/` | Proposal 演示资料 |

系统整体边界见 [架构文档](docs/architecture.md)，前端页面与演示说明见 [frontend/README.md](frontend/README.md)。
