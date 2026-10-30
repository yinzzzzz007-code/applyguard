# 第二轮 UI / UX 精修

## 方向与研究

继承用户的四种主色及 Apple 风格。参考 UV Mapper 的“可读状态 → 明确指引 → 就近操作”，将它用于岗位、证据和申请流程；没有给申请工具强加地图或天气功能。

- [UV Mapper：红点官方](https://www.red-dot.org/project/uv-mapper-83181)：参考其功能分组及状态就近呈现。属于 2025 Design Concept / Next Gen Award 概念作品，未声称是已验证的量产产品或 Best of the Best。
- [设计师案例](https://devinwang.net/uv-mapper)：了解其场景、路径指引与核心操作，不挪用其用户调研比例作为 ApplyGuard 的证据。
- [Jakob Nielsen：Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)：将原文、预检和版本按任务分开，次要的高频需求报告放到后面。
- [NN/g：Visibility of System Status](https://www.nngroup.com/articles/visibility-system-status/)：明确结果数、选中岗位、处理中、无结果及重试方向。
- [Apple：Design intuitive search experiences](https://developer.apple.com/videos/play/wwdc2026/292/)：为收藏和经历增加易发现的搜索入口与清除操作。
- [Dieter Rams：Good design](https://www.vitsoe.com/us/about/good-design)：作为有用、易理解、克制和细节一致的设计原则参考。
- [W3C：Tabs Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)：标签具有选中状态和关联面板，支持左右方向键及 Home / End。

这些资料指导设计判断；本次没有招募真实用户，也没有测得任务耗时或错误率的改善百分比。

## 技能逐项应用

1. frontend-design：将本轮目标确定为“找到机会、看清缺口、方便行动”，先排常用操作，再做表面质感。
2. awesome-design-md / Apple：复核字体层级、24px 模块间距、浅色工作区与蓝色主要操作；该仓库作为规范资料使用。
3. ui-ux-pro-max：查询搜索、筛选、移动列表详情规则；增加组合关键词、清除、排序、结果数及手机返回。
4. Understand-Anything / understand-explain：按其文件、导入、层级结构生成前端静态导入图，36 个模块、114 条导入边；针对 JobRadarPage → api/jobs → DemoContext、ResumeReviewPage → SAGPolishPanel 走查。图在 .ua/knowledge-graph.json，保留源码指纹。没有 Git 提交元数据，因此按文件哈希核对新鲜度；它是局部结构图，不是官方完整多阶段全仓语义分析。
5. taste：复用 framed-sheet，seed 1874992603；以岗位和证据为主内容，保留用户指定色板，移走首屏次要报告。
6. impeccable：context、polish、craft-floor 以及一次最终 detect。没有安装或启用自动 hooks。

## 具体改动

- 岗位：跨字段组合关键词；来源状态快速筛选；未归档 / 准备中 / 已归档 / 全部；最近导入和公司排序；无结果重置；选中岗位被筛掉后显示当前结果中的岗位。
- 详情：分开岗位原文、证据预检和版本；每个版本结果绑定其岗位；陈述预检继续绑定岗位 ID、内容指纹和经历签名。关闭、归档和参考岗位继续禁止准备申请。
- 手机：岗位列表与详情分别呈现，提供返回按钮，返回后恢复列表焦点。
- 简历：可搜索、按类型筛选来源；显示实际条数和字符数；空草稿不能进入陈述核验；底部保留下一步入口。
- 润色：原稿与建议分组；异常显示可重试提示并保留原稿；历史与核验门禁保持原有语义。
- 通用：切换演示场景前提示工作流会清空；手机导航支持 Escape；材料库显示筛选结果与总量。

## 验证记录

- build 通过；smoke 通过，19 项测试，其中新增 3 项验证搜索、范围与排序。
- lint：0 error，3 条已有警告，未新增。
- Impeccable detect：[]。
- taste 应用源码 lint：0 FAIL，11 WARN。警告来自指定蓝色及真实浮层阴影，按原设计保留。
- 浏览器：组合搜索、筛掉选中项后的详情、无结果重置、键盘切换标签、预检空分类、读取版本、手机进入详情和返回、经历搜索与选入、空草稿禁用、未核验陈述不能继续。
- 390px 和 1440px 岗位页未见页面横向溢出。截图使用独立服务 8871 和仓库自带虚构数据；没有写入或打包用户当前的简历、岗位或证据数据。

未完成跨浏览器、真实设备、完整读屏和真实用户对照实验。本轮未调用付费模型，也没有重新测量 SAG 的事实核验性能。没有运行 taste 浏览器 inspector；浏览器验证通过当前工具进行。

## 已知界限与恢复

岗位搜索词和收藏范围保存在当前标签页 sessionStorage，不保存岗位正文。完整工作流仍为页面内状态，刷新可能丢失尚未应用的建议；本轮交付时保留用户原标签页，不强制刷新。

更新前备份被修改的源码与构建入口；旧构建资源保留，以便回滚。PRODUCT.md 可另行通过 impeccable init 补齐其专用格式，本轮不扩大范围。
