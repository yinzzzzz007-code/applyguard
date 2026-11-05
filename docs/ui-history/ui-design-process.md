# 界面改版记录

日期：2026-10-29。基于上一轮 SAG 集成实验版进行前端改版。

## 参考与技能

按 1 → 3 → 2 → 4 → 5 读取和应用，再以 impeccable 精修。

1. frontend-design：先确定安静的申请工作台，保留 React、业务数据和核验约束。
2. awesome-design-md：采用其 Apple 规范中的系统字体、浅色画布、清晰字号层级、少量蓝色操作。该项目是资料库，不是可执行技能；实际规则记录在根目录 DESIGN.md。
3. ui-ux-pro-max：运行 design-system 与 React 可访问性检索。检索的 Minimalism 方向适用，但自动返回的营销页模式和青色配色不适合本项目，未采用；用户指定配色优先。
4. Understand-Anything：安装 understand / understand-explain。围绕 AppShell、DemoContext、SAGPolishPanel、原子事实显示和历史恢复走查依赖与数据流。没有执行全仓交互知识图谱流水线；本轮解释依据实际源码，不冒充完整图谱分析。
5. taste-skill：运行 --app --kind builder，选 framed-sheet，seed 855710088。保留其浅色工具框架、白色工作表与克制用色，按 BMO 参考和用户要求调整外框、蓝色主操作及紫色润色标记。运行源码 lint，紫色按用户明确要求记录例外。
6. impeccable：官方 context 成功；读取 polish / craft-floor，完成精修。按 context 要求执行一次 detect，结果 []，见 ui-impeccable-detect.json。没有启用自动 hooks。

## 红点原始参考

- FIT Platform：官方页面明确 Best of the Best。https://www.red-dot.org/project/fit-platform-72252
- BMO：官方页面为 Red Dot Award。https://www.red-dot.org/project/bmo-re-imagines-digital-banking-experience-for-small-and-medium-enterprise-sme-clients-71875
- AI Ad Manager：官方页面为 Red Dot Award。https://www.red-dot.org/project/ai-ad-manager-71881

主参考 BMO 的浅色侧栏、窄顶栏、主辅分栏；FIT 参考模块化组织；AI Ad Manager 参考跨设备重排。没有把三种视觉逐像素叠在一起，也没有声称 1:1 复刻。未使用这些产品的商标、红点奖章或展示图作为 ApplyGuard 产品素材。

## 实现与界限

重做应用外框及导入页，调整简历审查为原稿 / 核验工具分栏，原文详情改为键盘可操作的 disclosure，核验页增加真实计数。上传控件保留原生 file input，可键盘访问。移除外部 Google Fonts 请求，加入统一图标及产品 favicon。

历史版本仍保留原来恢复文字后重新核验的行为。SAG 请求、陈述阻断、人工确认和导出逻辑未在此次改版中改变。未调用付费模型，没有重新测量 SAG 的事实准确率。

旧 index.css 保留未重构页面布局，workspace.css 负责新视觉层。后续可逐页迁移旧样式；当前以浏览器实际计算结果为准。全仓旧组件仍存在 3 条 lint 警告，未把其混入本轮功能修改。

## 验证

- npm run build：通过。
- npm run smoke：SMOKE_MOCK_PASSED，16 项测试通过。
- npm run lint：0 error，3 条现有警告（DemoContext 热更新、CareerVault 的 ref / effect）。
- Impeccable detect：[]。
- taste 源码检查：0 FAIL，11 WARN。蓝色来自用户指定色板；两处阴影均用于真实浮层（场景菜单、手机导航）。未把这些启发式提示当作质量认证。
- 浏览器实测：导入入口、经历库、岗位说明 → 离线工作流 → 证据匹配 → 简历审查；选入 / 手动添加 / 移出、原文展开、陈述核验阻断。
- 390px：导入页无横向溢出、侧栏折叠、文件输入有可访问名称；导航可进入证据工作区。
- 375px 与 768px：导入页无页面横向溢出，侧栏折叠。
- 1440px：原稿 / 核验工具分栏，无页面横向溢出。
- 宽屏默认 1280px：最终截图保存在 ui-preview.png。浏览器缩放及视口截图工具曾出现帧尺寸异常，异常截图不作为交付截图。

未执行原生手机设备、Safari、全站读屏或所有旧页面状态的完整验收；也未运行 taste 的浏览器 inspector。使用当前获准浏览器工具实测、源码 lint 和 impeccable detect，不能称为全部自动视觉标准通过。

核心静态配色对比度：#334155 / #F8FAFC 为 9.90:1；#64748B / #F8FAFC 为 4.55:1；白字 / #2563EB 为 5.17:1；#9333EA / 白底为 5.38:1。这不等同于全站所有旧组件状态的可访问性审计。

技能格式提示：Impeccable context 指出 PRODUCT.md 没有其专用 schema stamp，可按需运行 init 补齐格式；本次未据此改写已确认的业务内容。
