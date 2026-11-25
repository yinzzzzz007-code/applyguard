# 录制顺序

本机录制入口：`E:\ApplyGuard-录制版\ApplyGuard.exe`。启动后也可用浏览器打开 `http://127.0.0.1:8800/`。录制目录保留三份简历测试中 01 的实际结果，原个人工作区没有清空。

历史回放不请求模型。只有点击新的润色、核验或 AI 面试操作才请求模型。新请求可能需要几分钟，录制可以剪掉等待；回放时应说明是之前保存的真实结果。模拟材料不能作为真实证明。

| 页面与操作 | 简短英文说明 |
|---|---|
| 首页 → 选择 01 号简历；如已有演示草稿，可先展示经历库 | I import a résumé and review the extracted experience. |
| 经历库 → 查看项目、技术和日期，可以编辑或新增 | The experience library keeps reusable, editable records. |
| 岗位说明 → 展示已解析的职责和任职要求 | ApplyGuard reads both the job duties and the qualifications. |
| 证据匹配 → 点开要求，查看关联项目和理由 | It finds relevant experience. Relevance does not mean every fact is verified. |
| 证据匹配 → 让 Harness 二次查找并补充经历 → 沿用有效授权再次查找 → 修改概括并加入本次简历草稿 | I search the approved sources again for missing experience. I review the summary and add it directly to this draft. |
| 证明材料 → 查看同项目原文及关联；选择目录后授权 Harness 才能运行新搜索 | I choose the search scope and authorize access. Returned passages stay pending until I review them. |
| 简历审查 → 历史版本 → 展开保存的润色对照；点击回放可恢复当时页面 | This is a saved result from an earlier model run. Yellow marks wording changes. |
| 对照原文和建议 → 采用、保留，或直接编辑；结束回放回到正常流程 | I can accept the suggestion, keep my wording, or edit it myself. |
| 陈述核验 → 历史版本 → 保存的核验结果；看 15% 与材料 10% 的对照和行号 | The draft says fifteen percent, but the project record says ten. ApplyGuard shows both passages. |
| 编辑数字后需要重新核验；也可跳过核验并确认个人稿 | I can correct the detail or keep a personal draft. My approval does not turn missing evidence into proof. |
| 简历生成 → 查看最终正文，下载 TXT、LaTeX，或打印 PDF | The export uses my final wording. LaTeX remains editable. |
| 生成面经 → 题单、一次一问、追问、评分和复练 | The interview follows my experience and the job. It asks follow-up questions and helps me practise weak areas. |

若进入回放，页面上方会显示“当前是历史回放”和“结束回放，保留当前正文”。旧核验只供查看；新的材料或修改后的正文需要重新核验。未连接 GitHub 或 Harness 时不会自动读取私人仓库或目录。

录制版通过右上角“模型设置”保存配置，重启后仍能读取。服务地址为 `https://api.chatanywhere.tech/v1`，模型为 `gemini-3.1-flash-lite-preview`，密钥使用自己的。录制前确认密钥输入框提示“已配置，留空保留”；只在启动进程中临时传入密钥不会跨重启保留。不要把密钥录进画面。

若出现“面经生成未完成”，先打开模型设置确认密钥是否仍已配置。2026-11-26 本机遇到的这一例是临时密钥随重启丢失，恢复并通过设置入口保存后，后端 `key_configured` 和健康检查的 `cloud_model_configured` 均为 true；服务鉴权为 HTTP 200，所选模型可用。该检查不等同于再次完成整份面经的计费测试。
