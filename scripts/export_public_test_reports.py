"""Export dated test evidence without publishing local sessions or credentials.

Gitvextor's prototype release utility. Original reports are never modified.
Only text reports are exported; screenshots, Harness profiles and session
archives stay local. Review the resulting Git diff before publishing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TEXT_TYPES = {".json", ".jsonl", ".md", ".log", ".txt"}
SECRET_KEY = re.compile(
    r"^(?:api[_-]?key|.*[_-]api[_-]?key|token|ui_token|access_token|"
    r"refresh_token|authorization|password|secret|pairing_code|"
    r".*[_-](?:TOKEN|SECRET|PASSWORD)|OPENAI_API_KEY)$", re.I
)
SECRET = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,})\b"
)
BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_.~+/-]{12,}=*")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE = re.compile(r"(?<!\d)(?:\+86[- ]?)?1[3-9]\d{9}(?!\d)")


def redact_text(text: str, aliases: list[tuple[str, str]]) -> str:
    text = SECRET.sub("[REDACTED_CREDENTIAL]", text)
    text = BEARER.sub("Bearer [REDACTED]", text)
    for original, replacement in aliases:
        text = text.replace(original, replacement)
        text = text.replace(original.replace("\\", "/"), replacement)
        text = text.replace(original.replace("\\", "\\\\"), replacement)
    text = re.sub(
        r'(?i)((?:[A-Za-z_]*api[_-]?key|[A-Za-z_]*token|authorization|'
        r'password|secret)["\x27]?\s*[=:]\s*["\x27]?)[^\s"\x27,;}]+',
        r"\1[REDACTED]", text,
    )
    text = re.sub(r"(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+", "[LOCAL_USER]", text)
    text = re.sub(r"(?i)[A-Z]:[\\/]+jianglingtian", "[LOCAL_USER]", text)
    text = re.sub(r"wxid_[A-Za-z0-9_]+", "[LOCAL_ACCOUNT]", text)
    text = EMAIL.sub("[REDACTED_EMAIL]", text)
    text = PHONE.sub("[REDACTED_PHONE]", text)
    return text.replace("姜凌天CV", "[PRIVATE_RESUME]").replace("姜凌天", "[PRIVATE_NAME]")


def redact_value(value, aliases):
    if isinstance(value, dict):
        return {
            redact_text(str(k), aliases):
            ("[REDACTED]" if SECRET_KEY.fullmatch(str(k)) and isinstance(v, str)
             else redact_value(v, aliases))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_value(v, aliases) for v in value]
    if isinstance(value, str):
        return redact_text(value, aliases)
    return value


def export(sources: list[tuple[str, Path]], destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    aliases = [(str(p.resolve()), f"[REPORT_SOURCE:{label}]") for label, p in sources]
    aliases += [(str(root), "[APPLYGUARD_ROOT]"), (str(Path.home()), "[LOCAL_USER]")]
    aliases.sort(key=lambda item: len(item[0]), reverse=True)
    manifest = {
        "exported_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "policy": "Text-only public copy; credentials, personal contacts and local paths redacted. "
                  "Original dates, failures, partial runs and source hashes retained. "
                  "Screenshots, profiles, databases and session archives excluded. "
                  "Export is not a new test run.",
        "files": [], "excluded_by_type": {},
    }
    excluded = Counter()
    runs = []
    for label, source in sources:
        if not source.is_dir():
            raise FileNotFoundError(f"Missing source group: {label}")
        for file in sorted(source.rglob("*")):
            if not file.is_file():
                continue
            relative = file.relative_to(source)
            if (file.suffix.lower() not in TEXT_TYPES or
                    any(part.lower() in {"sessions", "profiles", "__pycache__"}
                        for part in relative.parts)):
                excluded[file.suffix.lower() or "(no extension)"] += 1
                continue
            raw = file.read_bytes()
            text = raw.decode("utf-8-sig", errors="replace")
            if file.suffix == ".json":
                try:
                    payload = json.loads(text)
                    public = redact_value(payload, aliases)
                    text = json.dumps(public, ensure_ascii=False, indent=2) + "\n"
                    if file.name == "report.json" and isinstance(public, dict):
                        runs.append((label + "/" + relative.parent.as_posix(),
                                     public.get("started_at", public.get("date", "see report")),
                                     public.get("status", "see report")))
                except json.JSONDecodeError:
                    text = redact_text(text, aliases)
            elif file.suffix == ".jsonl":
                lines = []
                for line in text.splitlines():
                    try:
                        lines.append(json.dumps(redact_value(json.loads(line), aliases),
                                                ensure_ascii=False))
                    except json.JSONDecodeError:
                        lines.append(redact_text(line, aliases))
                text = "\n".join(lines) + "\n"
            else:
                text = redact_text(text, aliases)
            if SECRET.search(text):
                raise ValueError(f"Unredacted credential pattern: {label}/{relative}")
            target = destination / label / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
            manifest["files"].append({
                "path": target.relative_to(destination).as_posix(),
                "original_sha256": hashlib.sha256(raw).hexdigest(),
                "public_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            })
    manifest["excluded_by_type"] = dict(excluded)
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    readme = [
        "# 2026-10-30 测试报告归档", "",
        "本目录是逐次测试记录的脱敏公开副本，原报告日期、失败、重试与中断状态均保留。",
        "导出不是重跑。模型效果、单元测试、构建与 UI 验收应分别阅读，不合并分母。",
        "密钥、授权令牌、私人联系方式和本机路径已脱敏；Harness 配置、会话档案和"
        "未复核截图不上传。文件原始/公开 SHA256 与排除类型见 [manifest.json](manifest.json)。",
        "", "main：功能实验版；ui：界面开发目录的历史回归；frozen-asu：冻结实验续跑。",
        "", "| 报告 | 开始时间（原记录） | 状态 |", "| --- | --- | --- |",
    ]
    for path, when, status in runs:
        readme.append(f"| [{path}]({path}/report.json) | {when} | {status} |")
    (destination / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    return {"files": len(manifest["files"]), "indexed_runs": len(runs),
            "excluded_by_type": dict(excluded)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, metavar="LABEL=PATH")
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args()
    inputs = [(label, Path(path)) for label, path in
              (item.split("=", 1) for item in args.source)]
    print(json.dumps(export(inputs, args.dest), ensure_ascii=False))
