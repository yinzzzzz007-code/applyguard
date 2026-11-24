# ApplyGuard 录制操作与英文读稿

本稿对应 2026-11-23 当前界面。云功能是否通过以 [最终测试记录](testing-report-2026-11-23-final-personal-flow.md) 为准；模型失败或规则回退不能讲成模型成功。建议录制 4–6 分钟，等待模型的片段可以加速，并标注“Waiting for the model”。

## 启动与准备

在项目文件夹打开终端，运行 `./start-demo.bat`；它启动后端 8000 和前端 5173。当前已经启动时直接打开 `http://127.0.0.1:5173/`。关闭用 `./stop-demo.bat`。先确认右上角“本地服务已连接”，这只说明后端连接正常。

公开演示可用 `eval/public-demo/public-demo-resume.pdf`、`atlas-evidence.md` 和 `job-description.txt`，候选人和经历均为虚构。该 PDF 已实际解析为 1 条教育、1 个项目，并渲染检查。材料的正确测试数是 12；将其改成 120 可演示错改检查，不能把这个小样例叫准确率评测。

如用自己的材料录给老师，先避开手机号、邮箱、完整证件、家庭／财务信息以及 API Key、Agent 令牌。不要录制终端输入 Key 的过程。

## 每一步的操作和讲解

| 步骤 | 中文操作与观察点 | 简洁英文说明 |
| --- | --- | --- |
| 1 首页 | 打开“简历导入”，说明材料到核验的主线。 | This is ApplyGuard, an evidence-based resume assistant. |
| 2 选择简历 | 点击“选择简历”，选择 PDF；等待 OCR／文字识别完成，展示分类数量和原文。 | I import a PDF resume. The system extracts the text and organizes the experience. |
| 3 一键带入 | 点击“导入到经历库”。观察自动跳转和未保存状态。 | The extracted information goes into an editable draft. It is not saved automatically. |
| 4 编辑并保存 | 在经历库核对卡片；改一个字段，点“完成编辑”，再点“保存经历库”。 | I review the details, correct any errors, and save my experience library. |
| 5 云朵引导 | 点页头“云朵引导”；或在禁用按钮旁点“查看原因与补全引导”。缺两项时，补齐较近的一项，展示云朵移到下一项。 | The blue guide explains what is missing and moves to the next step after I complete it. |
| 6 添加材料 | 进入“证明材料”，上传相关证明，打开原件和识别正文，核对并关联到经历。 | I add supporting documents and link them to the relevant experience. |
| 7 可选 Agent | 展开“连接 DeepSeek Harness / 其他 Agent”，连续选具体文件夹，亲自选外发规则，生成授权，再在本机执行启动命令。待实际回传后再确认导入。 | With my permission, a local agent can find relevant source material. I review each returned quote before importing it. |
| 8 可选 GitHub | 点击“从 GitHub 查找材料”，输入用户名、公开邮箱或关键词，选择公开仓库；展示固定的提交版本。 | I can also select a public GitHub repository. The source is pinned to a specific commit. |
| 9 岗位准备 | 进入“岗位说明”，粘贴岗位描述。选择 AI 模式并确认分析；打开证据匹配，查看匹配项和缺口。 | I enter a target job description and compare its requirements with my experience and evidence. |
| 10 AI 润色 | 在“简历审查”点击“按目标岗位润色简历”；阅读页面内“确认使用模型”，点“同意并开始”。展示原句、建议句和证据，逐句决定采用。 | AI improves the wording for the target role. I compare the suggestion with the original and its evidence. |
| 11 故意错误 | 展示一处与证明不符的数字。在文本框自行修改、刷新确认暂存未丢，再点“保存修改”。观察“当前文字待核验”。 | Here, the number conflicts with the source. I correct it manually, and the previous check becomes outdated. |
| 12 重新核验 | 点击“用 AI 重新核验”或“AI 检查材料支持”，确认后等待。打开陈述核验的原子事实和引用。 | The system checks the updated statement against source quotes. Confirmation alone does not make a fact verified. |
| 13 导出分支 | 展示两种策略的区别。有缺依据的内容，严格导出应被阻止；用户确认稿保留未核验记录。只在实际通过时展示已核验稿。 | Verified export requires current evidence checks. A user-confirmed draft keeps unresolved issues in its review record. |
| 14 面经 | 进入“生成面经”，确认模型使用，点击“生成自我介绍与模拟问答”；展示项目覆盖。 | The interview guide creates introductions and project-specific practice questions. |
| 15 岗位雷达 | 进入“岗位雷达”，刷新官网；点击“未读提醒”→一条消息→岗位详情，再打开“新增岗位”。 | The job radar refreshes supported official sources and lets me inspect each notification. |
| 16 推荐与反馈 | 展示“为你推荐（语义与兴趣）”和推荐理由；点“感兴趣”，再展示可撤销。 | Jobs are ranked by resume relevance, preferences, and feedback. The score is not a hiring probability. |

## 字幕与配音

先只录屏，不必同时念。把上表英文逐句作为字幕，在剪辑软件中对齐对应操作；每句保留约 4–8 秒，长句拆两行。需要 AI 配音时，可将英文按步骤逐句生成语音，再按画面调时长。不要先固定整段 SRT 时间轴：网络等待长短不同，先剪好视频再对齐字幕。

结尾可读：**ApplyGuard helps me explain my work clearly, while keeping evidence, uncertainty, and personal decisions visible.**

如果本次服务返回 503／超时，保留错误反馈镜头并说明：**The model service is unavailable, so the original draft is preserved.** 该状态不作为完整模型流程通过的证据。

云朵提示会随当前页面变化；关闭后可用页头“云朵引导”重新打开，不会清空完成记录。若按钮缺条件，点旁边的补全引导会优先定位缺项；切换页面后不会沿用上一页缺项。修复验证见 [按页面引导报告](testing-report-2026-11-23-cloud-guide-pages.md)。
