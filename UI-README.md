# ApplyGuard 工作台界面

2026-10-30，由姜凌天（Gitvextor）整合当前界面与 SAG V2。包含岗位组合搜索与筛选、简历来源搜索、原子事实依据、润色建议差异及浏览器最近 20 版回滚。新增内容和测试见 [发布说明](docs/release-2026-10-30-gitvextor.md)。

## 本机启动

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
.\preview-ui.cmd
```

打开 http://127.0.0.1:8870 。服务在当前终端运行，Ctrl+C 停止；可使用 `preview-ui.ps1 -Port 8871` 指定端口。Git 仓库不包含构建文件，需要先构建。

SAG 模型实验另按 [集成说明](docs/sag-grounding.md) 安装并配置。基础离线演示无需密钥；密钥仅由本地后端读取，不能提交。设计约定见 [DESIGN.md](DESIGN.md)。
