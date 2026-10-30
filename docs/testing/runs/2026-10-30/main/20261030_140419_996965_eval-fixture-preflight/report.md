# 检查报告：eval-fixture-preflight

- 日期时间：2026-10-30T14:04:19.996965+08:00 — 2026-10-30T14:04:20.459208+08:00（北京时间）
- 范围：[APPLYGUARD_ROOT]
- 命令：`[LOCAL_USER]\.codex\visualizations\2026\10\29\01a18641-01a9-7e31-85a7-f651b4b504af\applyguard-sag-app\.venv\Scripts\python.exe -c import sys,json; sys.path.insert(0,"scripts"); import resume_expanded_eval as r; from pathlib import Path; d=json.loads(Path(r"[LOCAL_USER]\.codex\visualizations\2026\10\29\01a18641-01a9-7e31-85a7-f651b4b504af\applyguard-frozen-resume-20261030\data\local\expanded-eval\frozen-dataset.json").read_text(encoding="utf8")); r.preflight(d); print("PASS: 9 contracts, 260 offline baseline cases, zero model calls")`
- 结果：PASS，退出码 0
- 耗时：0.462秒
- 输出见 test.log；源文件 SHA256 见 report.json。
- 限制：构建通过不等于浏览器交互通过；用例数量以日志为准。
