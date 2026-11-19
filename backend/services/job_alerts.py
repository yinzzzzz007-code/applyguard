from __future__ import annotations

from urllib.parse import parse_qs, urlsplit


def emit(conn, key, source_id, job_id, kind, reason, level, stamp):
    conn.execute(
        """INSERT OR IGNORE INTO job_alerts
        (event_key,source_id,job_id,kind,reason,match_level,created_at)
        VALUES (?,?,?,?,?,?,?)""", (key, source_id, job_id, kind, reason, level, stamp))
    # A later version may notify again; reopening a previous version is an explicit user action.


def list_alerts(conn, path):
    query = parse_qs(urlsplit(path).query)
    conditions, values = [], []
    if query.get("job_id"):
        conditions.append("a.job_id=?")
        values.append(query["job_id"][0])
    if query.get("unread") == ["true"]:
        conditions.append("a.read_at IS NULL")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = conn.execute(
        """SELECT a.*, json_extract(o.payload,'$.title') AS title
        FROM job_alerts a LEFT JOIN opportunities o ON a.job_id=o.id"""
        + where + " ORDER BY a.created_at DESC, a.event_key LIMIT 200", values)
    items = [{**dict(row), "is_read": row["read_at"] is not None} for row in rows]
    unread = conn.execute("SELECT count(*) FROM job_alerts WHERE read_at IS NULL").fetchone()[0]
    return {"items": items, "unread": unread}


def mark(conn, request, stamp, *, all_alerts=False):
    if all_alerts:
        return {"changed": conn.execute("UPDATE job_alerts SET read_at=? WHERE read_at IS NULL", (stamp,)).rowcount}
    ids = request.get("ids")
    job_id = request.get("job_id")
    unread = request.get("unread", False)
    if type(unread) is not bool:
        raise ValueError("unread 必须为布尔值")
    if job_id and not ids and isinstance(job_id, str) and len(job_id) <= 40:
        cursor = conn.execute("UPDATE job_alerts SET read_at=? WHERE job_id=?", (None if unread else stamp, job_id))
    elif isinstance(ids, list) and 1 <= len(ids) <= 200 and all(isinstance(item, str) and len(item) <= 180 for item in ids):
        placeholders = ",".join("?" for _ in ids)
        cursor = conn.execute(f"UPDATE job_alerts SET read_at=? WHERE event_key IN ({placeholders})", (None if unread else stamp, *ids))
    else:
        raise ValueError("请提供 1 至 200 个提醒编号，或一个岗位编号")
    return {"changed": cursor.rowcount}
