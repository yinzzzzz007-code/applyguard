from __future__ import annotations

from urllib.parse import parse_qs, urlsplit


def emit(conn, key, source_id, job_id, kind, reason, level, stamp):
    conn.execute(
        """INSERT OR IGNORE INTO job_alerts
        (event_key,source_id,job_id,kind,reason,match_level,created_at)
        VALUES (?,?,?,?,?,?,?)""", (key, source_id, job_id, kind, reason, level, stamp))
    # A later version may notify again; reopening a previous version is an explicit user action.


def list_alerts(conn, path, ranks=None):
    query = parse_qs(urlsplit(path).query)
    conditions, values = [], []
    if query.get("job_id"):
        conditions.append("a.job_id=?")
        values.append(query["job_id"][0])
    if query.get("unread") == ["true"]:
        conditions.append("a.read_at IS NULL")
    try:
        offset = int(query.get("offset", ["0"])[0])
        limit = int(query.get("limit", ["200"])[0])
    except (ValueError, TypeError):
        raise ValueError("提醒分页参数必须为整数") from None
    if not 0 <= offset <= 100000 or not 1 <= limit <= 200:
        raise ValueError("提醒分页须为 offset 0–100000、limit 1–200")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    ordering, params = "a.created_at DESC, a.event_key", []
    if ranks is not None:
        import json
        ordering = "CASE WHEN a.job_id IS NULL THEN -1 ELSE COALESCE(r.value, 2147483647) END, " + ordering
        rank_join = " LEFT JOIN json_each(?) AS r ON r.key=a.job_id "
        params.append(json.dumps(ranks))
    else:
        rank_join = ""
    rows = conn.execute(
        """SELECT a.*, json_extract(o.payload,'$.title') AS title
        FROM job_alerts a LEFT JOIN opportunities o ON a.job_id=o.id"""
        + rank_join + where + " ORDER BY " + ordering + " LIMIT ? OFFSET ?", [*params, *values, limit, offset])
    items = [{**dict(row), "is_read": row["read_at"] is not None} for row in rows]
    unread = conn.execute("SELECT count(*) FROM job_alerts WHERE read_at IS NULL").fetchone()[0]
    total = conn.execute("SELECT count(*) FROM job_alerts a" + where, values).fetchone()[0]
    return {"items": items, "unread": unread, "total": total, "offset": offset, "has_more": offset + len(items) < total}


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
