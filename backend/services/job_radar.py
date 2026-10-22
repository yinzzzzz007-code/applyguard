"""Local opportunity library and read-only adapter for AI Career Radar's public API.

Independently implemented; no upstream source, scoring or personal profile is bundled.
Opportunity text is untrusted input, never candidate evidence.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from backend.services.local_store import local_dir

STATUSES = {"open", "closed", "unknown", "reference"}
STAGES = {"saved", "preparing", "archived"}
MAX_JOBS = 100
# General-purpose aliases authored for ApplyGuard, not an upstream configuration copy.
FACTORS = (
    ("python", "Python", "技术", ("Python",)),
    ("cpp", "C++", "技术", ("C++", "C/C++")),
    ("torch", "深度学习框架", "技术", ("PyTorch", "TensorFlow", "深度学习框架")),
    ("llm", "大语言模型", "技术", ("LLM", "大语言模型", "大模型")),
    ("multimodal", "多模态", "技术", ("multimodal", "多模态", "vision-language")),
    ("agent", "智能体", "技术", ("LLM agent", "agentic", "智能体", "工具调用")),
    ("rag", "检索增强", "技术", ("RAG", "检索增强", "retrieval augmented")),
    ("systems", "训练与推理系统", "技术", ("CUDA", "分布式训练", "vLLM", "推理引擎")),
    ("web", "接口开发", "技术", ("HTTP API", "FastAPI", "接口服务", "后端开发")),
    ("testing", "自动化测试", "技术", ("automated tests", "unit tests", "自动化测试", "单元测试")),
    ("deployment", "部署与落地", "能力要求", ("部署", "上线", "deployment", "production")),
    ("research", "研究与论文", "能力要求", ("论文", "publication", "research experience", "研究经历")),
    ("degree", "学历", "背景要求", ("本科", "硕士", "博士", "bachelor", "master", "PhD")),
    ("opensource", "开源协作", "能力要求", ("开源", "open source", "GitHub")),
)


class RadarUnavailable(ValueError):
    """Upstream unavailable; preserve all local opportunities."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _text(value: Any, field: str, limit: int = 200, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"{field} 必须是字符串且不超过 {limit} 字符")
    value = value.strip()
    if required and not value:
        raise ValueError(f"请填写 {field}")
    return value


def _description(value: Any, field: str) -> str:
    value = _text(value, field, 18000)
    # Preserve plain-text comparisons (e.g. C++ < 3 years); parse only recognizable tags.
    if re.search(r"</?(?:p|div|br|li|ul|ol|h[1-6]|span|a|b|strong|script|style)\b", value, re.I):
        parser = _PlainText()
        parser.feed(value)
        value = "".join(parser.parts)
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def _url(value: Any) -> str:
    value = _text(value, "来源链接", 2000)
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("来源链接格式无效") from exc
    if (parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username
            or parsed.password or any(ord(c) < 33 for c in value) or port == 0):
        raise ValueError("来源链接只接受无账号密码的 http/https 地址")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def jd_text(job: dict[str, Any]) -> str:
    return (f"{job['title']}\n公司：{job['company']}\n"
            + (f"地点：{job['location']}\n" if job["location"] else "")
            + job["description"])


def normalize(raw: Any, *, radar: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("每个岗位必须是 JSON 对象")
    title = _text(raw.get("title"), "岗位名称", required=True)
    company = _text(raw.get("company"), "公司", required=True)
    description = _description(raw.get("description") or raw.get("jd_text"), "JD 原文")
    if not description:
        responsibilities = _description(raw.get("responsibilities"), "岗位职责")
        requirements = _description(raw.get("requirements"), "任职要求")
        if responsibilities and responsibilities == requirements:
            # Some ATS adapters store the complete page in both fields.
            description = responsibilities
        else:
            description = "\n".join(part for part in (
                "岗位职责：\n" + responsibilities if responsibilities else "",
                "任职要求：\n" + requirements if requirements else "") if part)
    if not 20 <= len(description) <= 18000:
        raise ValueError("JD 原文需为 20 至 18000 字符；请导入包含完整职责/要求的岗位详情")
    source_kind = _text(raw.get("source_kind"), "来源类型", 80) or ("radar" if radar else "manual")
    status = raw.get("status", "unknown")
    if status is None or status == "":
        status = "unknown"
    if source_kind == "peer_benchmark":
        status = "reference"
    if not isinstance(status, str) or status not in STATUSES:
        raise ValueError("岗位状态只接受 open、closed、unknown 或 reference")
    job = {"title": title, "company": company, "description": description,
           "url": _url(raw.get("url")), "status": status, "source_kind": source_kind,
           "source_namespace": _text(raw.get("source_namespace"), "来源命名空间", 100) or ("radar" if radar else "import"),
           "external_id": _text(str(raw.get("external_id") or raw.get("id") or ""), "外部编号", 150),
           "source_observed_at": _text(raw.get("last_seen_at") or raw.get("source_observed_at"), "来源观察时间", 100)}
    for key in ("location", "education", "experience", "recruitment_type"):
        job[key] = _text(raw.get(key), key) or ""
    if len(jd_text(job)) > 20000:
        raise ValueError("岗位合并文本超过工作流上限")
    identity = ([job["source_namespace"], company.casefold(), job["external_id"]] if job["external_id"]
                else ["url", job["url"]] if job["url"] else
                ["manual", company.casefold(), title.casefold(), job["location"].casefold()])
    identity = ["reference" if status == "reference" else "opportunity", *identity]
    job["identity_key"] = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
    job["content_hash"] = hashlib.sha256(json.dumps(job, ensure_ascii=False, sort_keys=True,
        default=str).encode()).hexdigest()
    return job


@contextmanager
def database():
    folder = local_dir()
    folder.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(folder / "job-radar.sqlite3", timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS opportunities (
              id TEXT PRIMARY KEY, identity_key TEXT UNIQUE NOT NULL, payload TEXT NOT NULL,
              version INTEGER NOT NULL, stage TEXT NOT NULL, created_at TEXT NOT NULL, imported_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS opportunity_versions (
              job_id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL, imported_at TEXT NOT NULL,
              PRIMARY KEY(job_id, version));
        """)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
    finally:
        conn.close()


def _view(row) -> dict[str, Any]:
    job = json.loads(row["payload"])
    job.update({key: row[key] for key in ("id", "version", "stage", "created_at", "imported_at")})
    job["workflow_jd_text"] = jd_text(job)
    job["factors"] = extract_factors(job["description"])
    return job


def get_job(job_id: str) -> dict[str, Any]:
    if not isinstance(job_id, str) or not re.fullmatch(r"job_[a-f0-9]{16}", job_id):
        raise ValueError("无效岗位编号")
    with database() as conn:
        row = conn.execute("SELECT * FROM opportunities WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise ValueError("Route not found")
        return _view(row)


def save_jobs(raws: Any, *, radar: bool = False) -> dict[str, Any]:
    if not isinstance(raws, list) or not 1 <= len(raws) <= MAX_JOBS:
        raise ValueError(f"每批请导入 1 至 {MAX_JOBS} 个岗位")
    # Validate the whole batch first. Invalid items cannot cause a partial import.
    jobs = [normalize(raw, radar=radar) for raw in raws]
    results, counts = [], {"created": 0, "updated": 0, "unchanged": 0}
    with database() as conn:
        for job in jobs:
            existing = conn.execute("SELECT * FROM opportunities WHERE identity_key=?", (job["identity_key"],)).fetchone()
            timestamp = now()
            encoded = json.dumps(job, ensure_ascii=False)
            if existing:
                job_id, version = existing["id"], existing["version"]
                if json.loads(existing["payload"])["content_hash"] == job["content_hash"]:
                    counts["unchanged"] += 1
                else:
                    version += 1
                    conn.execute("UPDATE opportunities SET payload=?, version=?, imported_at=? WHERE id=?",
                                 (encoded, version, timestamp, job_id))
                    counts["updated"] += 1
            else:
                job_id, version = "job_" + uuid.uuid4().hex[:16], 1
                conn.execute("INSERT INTO opportunities VALUES(?, ?, ?, ?, 'saved', ?, ?)",
                             (job_id, job["identity_key"], encoded, version, timestamp, timestamp))
                counts["created"] += 1
            conn.execute("INSERT OR IGNORE INTO opportunity_versions VALUES(?, ?, ?, ?)",
                         (job_id, version, encoded, timestamp))
            results.append(_view(conn.execute("SELECT * FROM opportunities WHERE id=?", (job_id,)).fetchone()))
    return {**counts, "items": results}


def extract_factors(text: str) -> list[dict[str, Any]]:
    # Tags describe text frequency, not mandatory requirements or candidate competence.
    lines = [line for line in text.splitlines() if not re.search(
        r"ignore.{0,20}instructions|system\s*:|忽略.{0,8}(指令|要求)|系统指令", line, re.I)]
    factors = []
    for slug, label, category, terms in FACTORS:
        evidence = []
        for line in lines:
            hits = [term for term in terms if re.search(
                r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", line, re.I)]
            if hits:
                evidence.append({"text": line, "terms": hits})
        if evidence:
            factors.append({"slug": slug, "label": label, "category": category, "evidence": evidence})
    return factors


def list_jobs(path: str) -> dict[str, Any]:
    query = parse_qs(urlsplit(path).query)
    search = query.get("q", [""])[0].casefold()
    stage = query.get("stage", [""])[0]
    with database() as conn:
        jobs = [_view(row) for row in conn.execute("SELECT * FROM opportunities ORDER BY imported_at DESC, id")]
    jobs = [job for job in jobs if (not stage or job["stage"] == stage) and (not search or search in
            " ".join(job[key] for key in ("title", "company", "location", "description")).casefold())]
    eligible = [job for job in jobs if job["stage"] != "archived" and job["status"] in {"open", "unknown"}]
    factors = [{"slug": slug, "label": label, "jobs": sum(any(f["slug"] == slug for f in job["factors"])
                for job in eligible)} for slug, label, _, _ in FACTORS]
    return {"items": jobs, "total": len(jobs), "stats": {
        "open": sum(job["status"] == "open" for job in jobs),
        "unknown": sum(job["status"] == "unknown" for job in jobs),
        "reference": sum(job["status"] == "reference" for job in jobs),
        "closed": sum(job["status"] == "closed" for job in jobs),
        "analyzed_jobs": len(eligible),
        "factors": sorted([f for f in factors if f["jobs"]], key=lambda f: -f["jobs"])},
        "notice": "仅统计本机收藏且未归档的在招/状态未知岗位；关键词出现不等于硬性条件或市场全量。"}


def set_stage(job_id: str, stage: Any) -> dict[str, Any]:
    if not isinstance(stage, str) or stage not in STAGES:
        raise ValueError("收藏阶段只接受 saved、preparing 或 archived")
    get_job(job_id)
    with database() as conn:
        conn.execute("UPDATE opportunities SET stage=? WHERE id=?", (stage, job_id))
    return {"job": get_job(job_id)}


def edit_job(job_id: str, raw: Any) -> dict[str, Any]:
    original = get_job(job_id)
    if not isinstance(raw, dict):
        raise ValueError("job 必须是对象")
    fields = {key: raw.get(key, original[key]) for key in
              ("title", "company", "location", "url", "status", "description")}
    job = normalize({**original, **fields, "source_kind": "local_edit", "source_observed_at": ""})
    # Local editing keeps the same identity; later official reimports can create a new revision.
    with database() as conn:
        row = conn.execute("SELECT * FROM opportunities WHERE id=?", (job_id,)).fetchone()
        job["identity_key"] = row["identity_key"]
        encoded = json.dumps(job, ensure_ascii=False)
        version, timestamp = row["version"] + 1, now()
        conn.execute("UPDATE opportunities SET payload=?, version=?, imported_at=? WHERE id=?",
                     (encoded, version, timestamp, job_id))
        conn.execute("INSERT INTO opportunity_versions VALUES(?, ?, ?, ?)", (job_id, version, encoded, timestamp))
    return {"job": get_job(job_id)}


def validate_target(request: dict[str, Any]) -> dict[str, Any] | None:
    target = request.get("target_job")
    if target is None:
        return None
    if not isinstance(target, dict):
        raise ValueError("target_job 必须是对象")
    job = get_job(target.get("id", ""))
    if job["content_hash"] != target.get("content_hash"):
        raise ValueError("岗位版本已变化，请回到岗位雷达重新载入并运行工作流")
    if job["workflow_jd_text"] != request.get("jd_text"):
        raise ValueError("岗位文本已编辑，请解除岗位关联或重新载入原文")
    if job["stage"] == "archived" or job["status"] in {"closed", "reference"}:
        raise ValueError("已关闭、参考快照或已归档岗位不能进入申请流程")
    if not isinstance(request.get("resume_draft"), dict):
        raise ValueError("请先导入简历或保存本机经历，再为收藏岗位准备申请；不能使用演示经历替代")
    return {key: job[key] for key in ("id", "title", "company", "url", "content_hash", "version",
                                     "source_kind", "source_observed_at", "imported_at", "status")}


def analyze_job(job_id: str, request: dict[str, Any]) -> dict[str, Any]:
    from backend.services.jd_parser import JDParser
    from backend.services.evidence_matcher import EvidenceMatcher
    from backend.services.local_evidence import attach_local_evidence
    from backend.services.resume_draft_vault import experiences_from_resume_draft
    from backend.services.claim_validator import ClaimValidator

    job = get_job(job_id)
    parsed, mode, _ = JDParser().parse(job["workflow_jd_text"])
    draft = request.get("resume_draft")
    if draft is not None and not isinstance(draft, dict):
        raise ValueError("resume_draft 必须是对象")
    experiences = attach_local_evidence(experiences_from_resume_draft(draft), draft) if draft else []
    matched = EvidenceMatcher().match(parsed, experiences) if experiences else {"matches": []}
    requirements = []
    for req in parsed["requirements"]:
        candidates = sorted([m for m in matched["matches"] if m["requirement_id"] == req["requirement_id"]],
                            key=lambda m: (m["ready_for_selection"], m["relevance_score"]), reverse=True)
        supported = []
        for match in candidates:
            if not match["ready_for_selection"]:
                continue
            claims = [claim for exp in experiences for claim in exp["claims"] if claim["claim_id"] in match["claim_ids"]]
            # Run the same claim guard used by applications; tags/keyword matches never verify facts.
            if claims and all(ClaimValidator().verify({**claim, "evidence_support_score": claim["confidence"],
                "requirement_ids": [req["requirement_id"]]}, experiences,
                experiences[0]["candidate_id"], matched)["state"] == "VERIFIED" for claim in claims):
                supported.append(match)
        best = (supported or candidates or [None])[0]
        requirements.append({**req, "coverage": "SUPPORTED" if supported else "NEEDS_EVIDENCE" if candidates else "NO_MATCH",
            "evidence_ids": best["evidence_ids"] if supported else [],
            "experience_ids": [m["experience_id"] for m in supported],
            "notes": best["missing_evidence"] if best else ["本次经历中未找到可用证据；这不等于不具备此能力。"]})
    return {"job_id": job_id, "content_hash": job["content_hash"], "analyzed_at": now(),
            "mode": mode, "has_resume": bool(experiences), "requirements": requirements,
            "supported": sum(r["coverage"] == "SUPPORTED" for r in requirements), "total": len(requirements),
            "factors": job["factors"], "notice": "离线预检查，不生成或修改经历；缺证不等于不合格，也不是录用概率。正式申请仍需完整校验。"}


def _radar_get(path: str) -> dict[str, Any]:
    base = os.getenv("APPLYGUARD_RADAR_BASE_URL", "http://127.0.0.1:8787").strip()
    try:
        parsed = urlsplit(base)
        port = parsed.port or 8787
    except ValueError as exc:
        raise ValueError("雷达地址无效") from exc
    # Literal loopback only: no arbitrary hosts, DNS rebinding, redirects or proxy forwarding.
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"} or parsed.username
            or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("APPLYGUARD_RADAR_BASE_URL 只接受本机 http://127.0.0.1:端口 或 http://[::1]:端口")
    conn = http.client.HTTPConnection(parsed.hostname, port, timeout=5)
    try:
        conn.request("GET", path, headers={"Accept": "application/json"})
        res = conn.getresponse()
        data = res.read(2_000_001)
        if res.status != 200 or len(data) > 2_000_000:
            raise RadarUnavailable("雷达返回错误或内容过大；本机收藏保持不变")
        result = json.loads(data)
        if not isinstance(result, dict):
            raise RadarUnavailable("雷达响应格式无效")
        return result
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise RadarUnavailable("无法读取本机 AI Career Radar，请先启动它（默认 8787 端口），或使用 JSON 导入；本机收藏保持不变") from exc
    finally:
        conn.close()


def radar_preview(path: str) -> dict[str, Any]:
    query = parse_qs(urlsplit(path).query)
    try:
        offset = int(query.get("offset", ["0"])[0])
    except ValueError as exc:
        raise ValueError("offset 必须是非负整数") from exc
    if not 0 <= offset <= 100000:
        raise ValueError("offset 超出范围")
    params = {"limit": 50, "offset": offset, "status": "open"}
    for key in ("search", "city", "education", "recruitment_type", "direction"):
        if query.get(key):
            params[key] = _text(query[key][0], key)
    data = _radar_get("/api/jobs?" + urlencode(params))
    items, total = data.get("items"), data.get("total")
    if not isinstance(items, list) or len(items) > 50 or type(total) is not int or total < 0:
        raise RadarUnavailable("雷达岗位列表格式无效")
    output = []
    for row in items:
        if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] < 1:
            raise RadarUnavailable("雷达岗位编号无效")
        output.append({"id": row["id"], "title": _text(row.get("title"), "岗位名称", required=True),
                       "company": _text(row.get("company"), "公司", required=True),
                       "location": _text(row.get("location"), "地点"), "url": _url(row.get("url")),
                       "last_seen_at": _text(row.get("last_seen_at"), "来源观察时间", 100)})
    return {"items": output, "total": total, "offset": offset,
            "notice": "从独立运行的本机雷达读取；选择后才导入完整 JD。上次观察时间不保证岗位当前仍有效，请核对官网。"}


def radar_import(request: dict[str, Any]) -> dict[str, Any]:
    ids = request.get("ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or any(type(i) is not int or i < 1 for i in ids):
        raise ValueError("请选择 1 至 20 个雷达岗位编号")
    if len(set(ids)) != len(ids):
        raise ValueError("岗位编号不能重复")
    rows = []
    for job_id in ids:
        row = _radar_get(f"/api/jobs/{job_id}")
        if row.get("id") != job_id:
            raise RadarUnavailable("雷达岗位详情编号不一致；未导入任何岗位")
        # Keep source namespace/official ID when provided. Local radar DB IDs are a fallback only.
        if not row.get("external_id"):
            row = {**row, "external_id": str(job_id), "source_namespace": "radar-local"}
        rows.append(row)
    return save_jobs(rows, radar=True)


def handle_get(path: str) -> dict[str, Any]:
    route = urlsplit(path).path
    if route == "/api/v1/jobs":
        return list_jobs(path)
    if route == "/api/v1/jobs/radar":
        return radar_preview(path)
    match = re.fullmatch(r"/api/v1/jobs/(job_[a-f0-9]{16})(/versions)?", route)
    if match:
        job = get_job(match[1])
        if match[2]:
            with database() as conn:
                versions = [{"version": row["version"], "imported_at": row["imported_at"],
                             "job": json.loads(row["payload"])} for row in conn.execute(
                    "SELECT * FROM opportunity_versions WHERE job_id=? ORDER BY version DESC", (job["id"],))]
            return {"items": versions}
        return {"job": job}
    raise ValueError("Route not found")


def handle_post(path: str, request: dict[str, Any]) -> dict[str, Any]:
    if path == "/api/v1/jobs":
        return save_jobs([request.get("job")])
    if path == "/api/v1/jobs/import":
        return save_jobs(request.get("jobs"))
    if path == "/api/v1/jobs/radar/import":
        return radar_import(request)
    match = re.fullmatch(r"/api/v1/jobs/(job_[a-f0-9]{16})/(stage|analyze|edit)", path)
    if match:
        if match[2] == "edit":
            return edit_job(match[1], request.get("job"))
        return set_stage(match[1], request.get("stage")) if match[2] == "stage" else analyze_job(match[1], request)
    raise ValueError("Route not found")
