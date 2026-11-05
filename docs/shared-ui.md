# 共享前端与发布方式（2026-10-30）

本地开发曾以 Windows 目录联接共享同一份 frontend，两个开发服务（8871 / 8897）读取同一套构建。此为开发机布局，不是运行前提。本分支直接提交实际前端源码和素材；正常克隆后 frontend 是普通目录，无需原开发机盘符或联接。

以功能实验版为基础合入通用新手引导和页面过渡，保留 Agent 连接、拒绝的润色建议、完整版本历史与恢复后重新核验。后端和用户数据不合并。

构建：在 frontend 运行 npm ci、npm run build。最终离线验证：26 项前端测试通过，构建通过，lint 0 错误 / 3 条既有警告。逐次记录见 [报告归档](testing/runs/2026-10-30/README.md)。

重新生成动画使用 scripts/build-kinetic-adapter.py，配乐使用 scripts/kinetic-score.mjs；上游原模板随 vendor/kinetic-reel 提交。字体、动画与音频许可见 [第三方声明](../THIRD_PARTY_NOTICES.md)。历史界面评审见 [ui-history](ui-history/README.md)，旧项目短片已改为通用新手引导。
