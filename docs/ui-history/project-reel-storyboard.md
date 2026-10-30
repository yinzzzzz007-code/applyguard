# 项目短片 / Kinetic reel / 24 秒

本轮按用户反馈将卡片轮播重做为动态排版作品。实际复用 MIT kinetic-reel 模板的 Canvas 绘制、逐字动画、粒子地形、流体纹理、WebGL 后期与转场核心；改为项目数据驱动的实时播放器。

| 时间（3 个项目） | 镜头与机制 | 转场 |
| --- | --- | --- |
| 0–3s | WORK / IN MOTION，逐字下落、描边字回声、粒子地形与镜头推进 | 高亮圆点展开 |
| 3–11s | BUILD，真实项目名称、职责、日期；原文词组按拍进入格点并连接，首项目约占全片三分之一 | 圆形展开进入，横向推移离开 |
| 11–16s | MAKE IT MATTER，流体着色器映入字形；原文分句逐行显现 | 0.5s 推移 |
| 16–21s | CONNECT，原文分句成为节点，连线与标记逐拍通过 | 0.55s 擦除 |
| 21–24s | EVERY WORD, SOURCED；整片展开为真实项目时长轨迹，唯一斜体旁白收尾 | 0.6s 百叶窗；24s 回到片头 |

两个项目分配 3–13s、13–21s；单项目为 3–21s。时间轴与章节按钮使用同一 projectStart 函数。所有段落函数由时间 t 唯一决定，没有随机实时状态。局部粒子噪声由确定公式生成。

字体使用本机托管的 Anton、Archivo Black、Instrument Serif（OFL），中文使用系统字体。保留用户蓝 #2563EB、紫 #9333EA、灰 #334155、白 #F8FAFC；电影区域额外使用中性近黑作为投影底。HUD 与英文大字是用户指定 kinetic-reel 的局部语法，工作台仍采用原设计体系。

## 内容与控制

文字仅来自当前简历项目或已保存草稿，未调用模型、未传出材料。只取原文，不生成业绩指标。原文关键词仅是文字索引，不代表技术掌握；带明显否定词的句子不做关键词格点。原文节选与限行均显示省略号，完整内容可展开阅读。这不是独立事实核验，原流程的核验与导出限制保持不变。

最多三个项目，可选择、更换、暂停、拖动或收起。离屏时停止计时并释放渲染器，页面隐藏时停止。等待渲染器与字体就绪后才计时。WebGL 不可用有原文回退与重试。减少动态效果下停留在静态镜头，可手动切章节。窄容器切为 4:5 竖版独立编排，宽容器为 16:9。

配乐由模板合成器适配为 24 秒、120 BPM 的本地 WAV；默认静音，点击才加载播放。播放时使用音轨时间同步画面，暂停、隐藏与离屏同步静音。无噪声扫频转场。已做时长、峰值、各段 RMS 数值检查；未作人工听感评审。

目前交付是应用内实时短片，没有运行上游 Puppeteer / ffmpeg 离线渲染链，未输出 MP4 文件。实时方式能随项目编辑同步更新。

## 技能循环

frontend-design（唯一视觉焦点）→ awesome-design-md Apple 参考（对齐与控件克制）→ ui-ux-pro-max（暂停与减少动态效果）→ Understand-Anything（沿 AppShell、DemoContext、表单与草稿 API 阅读源码，未重做完整语义图）→ taste-skill（应用界面和局部作品分别评审）→ impeccable animate / polish（预算、空错状态、响应式、逐镜复查）。根据用户反馈，第二个循环替换了第一版的卡片舞台。

上游：[kinetic-reel](https://github.com/tuzhechen2005/opus-video-skills/tree/59744a69c7b916cfbe4c4ec84006b0c2f5e2fde1/skills/kinetic-reel)，提交 59744a69c7b916cfbe4c4ec84006b0c2f5e2fde1，2026-09-27。参考副本与许可证见 vendor/kinetic-reel、THIRD-PARTY-NOTICES.md；适配构建脚本为 scripts/build-kinetic-adapter.py，配乐脚本为 scripts/kinetic-score.mjs。

[W3C Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) 用于自动循环可控性；[UV Mapper](https://www.red-dot.org/project/uv-mapper-83181) 延续信息与行动就近组织的参考。未复用其品牌资产。

真实 PDF 的重复标题及研究段落硬换行会在展示层整理，完整原文保留；不把不完整的一行当作一个事实句。
