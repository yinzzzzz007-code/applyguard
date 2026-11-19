from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.services import job_alerts, job_matching, job_radar
from backend.services.job_sources.registry import SOURCES
from backend.services.local_store import load_resume_draft

try:
    SHANGHAI = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:
    SHANGHAI = timezone(timedelta(hours=8), "Asia/Shanghai")

LEASE = timedelta(minutes=6)
COOLDOWN = timedelta(minutes=5)


def instant():
    return datetime.now(timezone.utc)


def stamp(time):
    return time.isoformat(timespec="seconds").replace("+00:00", "Z")


def next_refresh(time, hours):
    hour, minute = map(int, os.getenv("APPLYGUARD_JOBS_REFRESH_TIME", "09:00").split(":"))
    local = time.astimezone(SHANGHAI)
    anchor = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    cadence = timedelta(hours=hours)
    return stamp((anchor + ((local - anchor) // cadence + 1) * cadence).astimezone(timezone.utc))


def source_rows(conn, time):
    enabled = {value.strip() for value in os.getenv("APPLYGUARD_JOB_SOURCES", ",".join(SOURCES)).split(",")}
    following = next_refresh(time, 24)
    today_slot = datetime.fromisoformat(following.replace("Z", "+00:00")) - timedelta(days=1)
    initial = stamp(today_slot) if today_slot.astimezone(SHANGHAI).date() == time.astimezone(SHANGHAI).date() else following
    for key in SOURCES:
        conn.execute("""INSERT OR IGNORE INTO job_sources(source_id, enabled, next_refresh_at)
            VALUES (?,?,?)""", (key, int(key in enabled), initial))
    return {row["source_id"]: dict(row) for row in conn.execute("SELECT * FROM job_sources")
            if row["source_id"] in SOURCES}


def reclaim(conn, time):
    conn.execute("""UPDATE job_refresh_runs SET state='interrupted',finished_at=?
        WHERE state='running' AND lease_until<=?""", (stamp(time), stamp(time)))


def view_run(row):
    return {**dict(row), "sources": json.loads(row["sources"]), "result": json.loads(row["result"])} if row else None


def status():
    with job_radar.database() as conn:
        time = instant()
        reclaim(conn, time)
        rows = source_rows(conn, time)
        current = conn.execute("SELECT * FROM job_refresh_runs WHERE state='running'").fetchone()
        last = conn.execute("""SELECT * FROM job_refresh_runs WHERE state!='running'
            ORDER BY started_at DESC, rowid DESC LIMIT 1""").fetchone()
        due = min((row["next_refresh_at"] for row in rows.values() if row["enabled"]), default=None)
        return {"state": "running" if current else last["state"] if last else "waiting",
                "current": view_run(current), "last": view_run(last), "next_refresh_at": due}


def list_sources():
    with job_radar.database() as conn:
        rows = source_rows(conn, instant())
        details = {row["source_id"]: row["total"] for row in conn.execute("""SELECT source_id,count(*) AS total
            FROM opportunities WHERE is_active=1 AND json_extract(payload,'$.details_available')=1 GROUP BY source_id""")}
        return {"items": [{**row, "enabled": bool(row["enabled"]), "name": SOURCES[key].source_name,
                            "company": SOURCES[key].company, "url": SOURCES[key].source_url,
                            "details_count": details.get(key, 0)}
                          for key, row in rows.items()], "ai_matching": job_matching.ai_enabled()}


def configure(source_id, request):
    if source_id not in SOURCES:
        raise ValueError("Route not found")
    time = instant()
    with job_radar.database() as conn:
        old = source_rows(conn, time)[source_id]
        enabled = request.get("enabled", bool(old["enabled"]))
        hours = request.get("interval_hours", old["interval_hours"])
        if type(enabled) is not bool or type(hours) is not int or hours not in {6, 12, 24, 48, 72, 168}:
            raise ValueError("启用值须为布尔值，刷新间隔支持 6、12、24、48、72、168 小时")
        next_at = next_refresh(time, hours) if hours in {6, 12, 24} else stamp(time + timedelta(hours=hours))
        conn.execute("UPDATE job_sources SET enabled=?,interval_hours=?,next_refresh_at=? WHERE source_id=?",
                     (int(enabled), hours, next_at, source_id))
    return list_sources()


def start(source_ids=None, *, force=False, due_only=False, background=True):
    if source_ids is not None and (not isinstance(source_ids, list) or not source_ids or
            any(not isinstance(key, str) or key not in SOURCES for key in source_ids)):
        raise ValueError("请指定有效的岗位源")
    if type(force) is not bool:
        raise ValueError("force 必须为布尔值")
    time = instant()
    with job_radar.database() as conn:
        reclaim(conn, time)
        if current := conn.execute("SELECT * FROM job_refresh_runs WHERE state='running'").fetchone():
            return {"run_id": current["id"], "state": "running", "joined": True}
        rows = source_rows(conn, time)
        keys = [key for key, row in rows.items() if row["enabled"] and (source_ids is None or key in source_ids)
                and (not due_only or row["next_refresh_at"] <= stamp(time))]
        if not force and not due_only:
            keys = [key for key in keys if max(rows[key]["last_success_at"] or "", rows[key]["last_failure_at"] or "")
                    <= stamp(time - COOLDOWN)]
        if not keys:
            return {"run_id": None, "state": "waiting", "message": "没有待刷新的启用来源。刚刷过时，可稍后重试或选择强制刷新。"}
        run_id = "refresh_" + uuid.uuid4().hex
        conn.execute("INSERT INTO job_refresh_runs(id,state,started_at,lease_until,sources) VALUES(?,'running',?,?,?)",
                     (run_id, stamp(time), stamp(time + LEASE), json.dumps(keys)))
    if background:
        threading.Thread(target=run, args=(run_id, keys), name="job-refresh", daemon=True).start()
        return {"run_id": run_id, "state": "running", "joined": False}
    return run(run_id, keys)


def latest_run(run_id):
    with job_radar.database() as conn:
        return view_run(conn.execute("SELECT * FROM job_refresh_runs WHERE id=?", (run_id,)).fetchone())


def collect(source_id):
    adapter = SOURCES[source_id]()
    with job_radar.database() as conn:
        adapter.previous = {row["external_id"]: json.loads(row["payload"]) for row in conn.execute(
            "SELECT external_id,payload FROM opportunities WHERE source_id=?", (source_id,))}
    snapshot = adapter.fetch()
    jobs, skipped = [], snapshot.skipped
    identities = set()
    for raw in snapshot.jobs:
        try:
            normal = job_radar.normalize(raw, source_id=source_id)
            if normal["identity_key"] not in identities:
                jobs.append(normal)
                identities.add(normal["identity_key"])
            else:
                skipped += 1
        except ValueError:
            skipped += 1
    if snapshot.jobs and not jobs:
        raise ValueError("官网岗位无法规范化")
    return jobs, snapshot.complete and skipped == snapshot.skipped, skipped, snapshot.notice


def record_source(conn, key, result, time):
    row = conn.execute("SELECT * FROM job_sources WHERE source_id=?", (key,)).fetchone()
    now = stamp(time)
    hours = row["interval_hours"]
    next_at = next_refresh(time, hours) if hours in {6, 12, 24} else stamp(time + timedelta(hours=hours))
    if result["errors"]:
        failures = row["consecutive_failures"] + 1
        conn.execute("""UPDATE job_sources SET last_failure_at=?,last_error=?,consecutive_failures=?,
                     next_refresh_at=? WHERE source_id=?""", (now, result["error"], failures, next_at, key))
        if failures >= 2:
            job_alerts.emit(conn, key + ":failure:" + (row["last_success_at"] or "initial"), key, None,
                            "source_failed", "官网连续刷新失败", None, now)
    else:
        count = conn.execute("SELECT count(*) FROM opportunities WHERE source_id=? AND is_active=1", (key,)).fetchone()[0]
        conn.execute("""UPDATE job_sources SET last_success_at=?,last_error=?,consecutive_failures=0,
            next_refresh_at=?,job_count=? WHERE source_id=?""",
            (now, result.get("notice"), next_at, count, key))


def save_snapshot(conn, key, jobs, complete, skipped, resume, time):
    now = stamp(time)
    result = dict(created=0, updated=0, closed=0, skipped=skipped, unchanged=0, errors=0, complete=complete)
    seen = set()
    for job in jobs:
        existing = conn.execute(
            """SELECT * FROM opportunities WHERE identity_key=? OR
               (source_id=? AND source_url<>'' AND json_extract(payload,'$.url')=?)
               ORDER BY (identity_key=?) DESC LIMIT 1""",
            (job["identity_key"], key, job["url"], job["identity_key"])).fetchone()
        if existing and existing["identity_key"] != job["identity_key"]:
            # Reuse the official URL's identity when the provider replaces its external ID.
            job["identity_key"] = existing["identity_key"]
        if existing and existing["id"] in seen:
            result["skipped"] += 1
            complete = False
            continue
        row, event = job_radar.write_job(conn, job, now, existing=existing)
        result[event] += 1
        seen.add(row["id"])
        match = job_matching.match_job(job, resume)
        conn.execute("""UPDATE opportunities SET payload=json_set(payload,'$.source_updated_at',?),
             source_id=?,source_url=?,observed_at=?,last_seen_at=?,
             is_new=CASE WHEN ?='created' THEN 1 ELSE is_new END,match_score=?,match_level=?,match_reasons=? WHERE id=?""",
            (job["source_updated_at"], key, job["source_url"], now, now, event, match["score"], match["level"],
             json.dumps(match, ensure_ascii=False), row["id"]))
        version_key = f"{row['id']}:{row['version']}"
        if event != "unchanged":
            kind, reason = ("new", "首次发现官网岗位") if event == "created" else (
                ("closed", "官网已标记该岗位失效") if job["status"] == "closed" else ("updated", "官网岗位内容更新"))
            job_alerts.emit(conn, f"{version_key}:{kind}", key, row["id"], kind, reason, match["level"], now)
        if match["level"] == "high" and job["status"] == "open" and row["stage"] != "archived":
            job_alerts.emit(conn, f"{version_key}:high", key, row["id"], "high", "本地规则评为高匹配", "high", now)
        try:
            days = (date.fromisoformat(job["closes_at"][:10]) - time.astimezone(SHANGHAI).date()).days
        except ValueError:
            days = -1
        if 0 <= days <= 3 and job["status"] == "open":
            job_alerts.emit(conn, f"{version_key}:closing", key, row["id"], "closing", "官网截止时间将至", match["level"], now)
    if complete:
        for row in conn.execute("SELECT * FROM opportunities WHERE source_id=? AND is_active=1", (key,)).fetchall():
            if row["id"] not in seen:
                raw = json.loads(row["payload"])
                job = job_radar.normalize({**raw, "status": "closed"}, source_id=key)
                changed, _ = job_radar.write_job(conn, job, now, existing=row)
                result["closed"] += 1
                conn.execute("UPDATE opportunities SET observed_at=? WHERE id=?", (now, row["id"]))
                job_alerts.emit(conn, f"{row['id']}:{changed['version']}:closed", key, row["id"], "closed",
                                "已从完整的官网岗位目录移除", row["match_level"], now)
    else:
        result["notice"] = "官网仅提供部分目录或部分记录未识别，保留历史岗位状态。"
    result["complete"] = complete
    return result


def run(run_id, keys):
    try:
        resume = load_resume_draft()
    except (OSError, ValueError):
        resume = None
    results = {}
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        tasks = {pool.submit(collect, key): key for key in keys}
        for future in as_completed(tasks):
            key, time = tasks[future], instant()
            try:
                jobs, complete, skipped, notice = future.result()
                with job_radar.database() as conn:
                    if not conn.execute("SELECT 1 FROM job_refresh_runs WHERE id=? AND state='running' AND lease_until>?",
                                        (run_id, stamp(time))).fetchone():
                        return {"run_id": run_id, "state": "interrupted"}
                    result = save_snapshot(conn, key, jobs, complete, skipped, resume, time)
                    if notice:
                        result["notice"] = notice
                    record_source(conn, key, result, time)
                    results[key] = result
                    conn.execute("UPDATE job_refresh_runs SET result=? WHERE id=?", (json.dumps(results), run_id))
            except Exception as exc:
                logging.warning("Official job refresh failed for %s (%s)", key, type(exc).__name__)
                error = str(exc) if isinstance(exc, ValueError) else "来源处理失败，请稍后重试。"
                result = dict(created=0, updated=0, closed=0, skipped=0, unchanged=0, errors=1, error=error[:240])
                with job_radar.database() as conn:
                    if not conn.execute("SELECT 1 FROM job_refresh_runs WHERE id=? AND state='running' AND lease_until>?",
                                        (run_id, stamp(time))).fetchone():
                        return {"run_id": run_id, "state": "interrupted"}
                    record_source(conn, key, result, time)
                    results[key] = result
                    conn.execute("UPDATE job_refresh_runs SET result=? WHERE id=?", (json.dumps(results), run_id))
    failures = sum(r["errors"] for r in results.values())
    state = "failed" if failures == len(keys) else "partial" if failures else "success"
    with job_radar.database() as conn:
        conn.execute("UPDATE job_refresh_runs SET state=?,finished_at=? WHERE id=? AND state='running'",
                     (state, stamp(instant()), run_id))
    return latest_run(run_id)


def start_scheduler():
    if os.getenv("APPLYGUARD_JOBS_AUTO_REFRESH", "true").lower() in {"0", "false", "off"}:
        return
    def schedule():
        while True:
            try:
                start(due_only=True, background=False)
            except Exception:
                logging.exception("Official jobs scheduler failed")
            threading.Event().wait(30)
    threading.Thread(target=schedule, name="job-refresh-scheduler", daemon=True).start()
