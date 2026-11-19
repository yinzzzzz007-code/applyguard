# ApplyGuard 设计规范

面向求职者的本地申请工作台。首要任务是整理经历、对照证据、修改简历和完成核验。界面应安静、准确、易操作。

## 视觉方向

工作台使用 StyleKit 水彩画风和参考图中的六色。大面积纸底为 `#FAF8F5`，主操作与焦点为 `#4A6FA5`，标题、正文和说明使用该蓝色的深色阶。桃色 `#E8A87C`、水青 `#85CDCA`、玫瑰 `#C38D94` 与赭色 `#D4A373` 用于低透明度晕染和状态辅助。状态文字使用对应颜色的深色阶。

页面上方叠三层静态水彩晕染，主要卡片用对角浅渐变。首页并排呈现 PDF 导入和 24 秒操作介绍，下面提供申请流程与课堂演示。窄屏依次显示导入、视频和说明。首页和帮助页共享同一段水彩导览，用原有 24 秒时间轴与四个章节内容。

## 字体与布局

工作台使用 Inter 或系统无衬线字体，字标和英文导览片头保留 Georgia。首页和内页统一使用 34–48px 粗体标题。用任务名称作为标题，说明写清操作步骤。主要卡片标题 22–26px，正文和页面说明 17px、行高 1.7，表单标签和按钮 15–16px，辅助信息 13–14px。间距以 8px 为单位，主要卡片内距 32px，标准卡片 24px，窄屏分别为 24px 和 16px。卡片使用 24px 圆角、1px 淡边线和柔和阴影。工作区内容最大 1080px。900px 及以下折叠导航，首页在 800px 及以下单列。主要按钮点击区域高度至少 44px。

编辑页采用草稿与核验工具分栏，长陈述完整显示，依据用原生 details 展开，避免只在悬浮时可见。导入页明确 PDF 限制与模型发送范围。图标使用统一 24px viewBox / 1.6px 线条。

## 交互与状态

每个页面保留一个主要任务。次要解释折叠；会影响材料发送、核验或导出的说明保持可见。已有的流程锁、阻断、重新核验、人工确认和历史恢复语义必须保留。未核验不展示通过。历史文字恢复后必须重核验。

提供键盘焦点、跳到主要内容、可访问文件输入和移动导航。胶囊按钮使用 500ms 缓动，悬停上移 2px，按下缩放至 98%。卡片晕染范围在 700ms 内变化。文本输入用蓝色焦点环和柔光提示。开启减少动态效果时，停用位移与过渡，导览可手动查看完整静止画面。空、失败、加载和禁用状态显示真实结果。

## 实施位置

`frontend/src/palette.css` 集中定义颜色。`workspace.css` 定义字体，`workspace-polish.css` 定义晕染、卡片和按钮反馈。`frontend/src/components/ui/` 复用 shadcn/ui Card 和 Button。导览画面位于 `WatercolorReelStage.tsx` 与 `motion.css`，播放器为 `ProjectReel.tsx`。使用 `npm run build`、`npm run smoke` 和 `scripts/home_browser_smoke.cjs` 检查构建及交互。

风格来源为 [StyleKit 水彩画风中文规范](https://www.stylekit.top/api/design/watercolor-style/design.md?locale=zh)。组件结构来自 [shadcn/ui Card](https://ui.shadcn.com/docs/components/base/card) 和 [Button](https://ui.shadcn.com/docs/components/radix/button)。

## 第二轮交互细化

参考 UV Mapper 的状态与行动就近组织，将预检、原文和版本放在选中岗位旁；常见要求报告移到次要位置。搜索、筛选、数量和重置一起呈现。手机岗位列表和详情采用两个视图。共享 Tabs 支持方向键、Home 和 End；共享 work-search 与 scope-switch 统一搜索与筛选控件。具体来源及验证记录见 docs/ui-round2-review.md。
