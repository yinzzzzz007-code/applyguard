from __future__ import annotations

import json


COLUMNS = {
    "source_id": "TEXT NOT NULL DEFAULT ''", "source_type": "TEXT NOT NULL DEFAULT 'manual'",
    "external_id": "TEXT NOT NULL DEFAULT ''", "source_url": "TEXT NOT NULL DEFAULT ''",
    "observed_at": "TEXT", "first_seen_at": "TEXT", "last_seen_at": "TEXT", "last_changed_at": "TEXT",
    "is_new": "INTEGER NOT NULL DEFAULT 0", "is_active": "INTEGER NOT NULL DEFAULT 1",
    "match_score": "INTEGER", "match_level": "TEXT", "match_reasons": "TEXT",
}


def migrate(conn):
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(opportunities)")}
    for column, spec in COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE opportunities ADD COLUMN {column} {spec}")
    if "source_id" not in existing:
        conn.execute("""UPDATE opportunities SET
            external_id=coalesce(json_extract(payload,'$.external_id'),''),
            source_type=coalesce(json_extract(payload,'$.source_kind'),'manual'),
            is_active=CASE WHEN json_extract(payload,'$.status') IN ('closed','reference') THEN 0 ELSE 1 END,
            first_seen_at=created_at, last_changed_at=imported_at""")
    statements = (
        """CREATE TABLE IF NOT EXISTS job_sources (
          source_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL, interval_hours INTEGER NOT NULL DEFAULT 24,
          last_success_at TEXT, last_failure_at TEXT, last_error TEXT, consecutive_failures INTEGER NOT NULL DEFAULT 0,
          job_count INTEGER NOT NULL DEFAULT 0, next_refresh_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS job_refresh_runs (
          id TEXT PRIMARY KEY, state TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
          lease_until TEXT NOT NULL, sources TEXT NOT NULL, result TEXT NOT NULL DEFAULT '{}')""",
        """CREATE UNIQUE INDEX IF NOT EXISTS job_refresh_single_active
          ON job_refresh_runs(state) WHERE state='running'""",
        """CREATE TABLE IF NOT EXISTS job_alerts (
          event_key TEXT PRIMARY KEY, source_id TEXT NOT NULL, job_id TEXT REFERENCES opportunities(id) ON DELETE CASCADE,
          kind TEXT NOT NULL, reason TEXT NOT NULL, match_level TEXT, created_at TEXT NOT NULL, read_at TEXT)""",
        "CREATE INDEX IF NOT EXISTS job_alerts_by_job ON job_alerts(job_id, read_at)",
        "CREATE INDEX IF NOT EXISTS job_opportunities_by_source ON opportunities(source_id, is_active)",
    )
    for sql in statements:
        conn.execute(sql)


def metadata(row):
    view = {key: row[key] for key in COLUMNS}
    for name in ("is_new", "is_active"):
        view[name] = bool(view[name])
    view["match_reasons"] = json.loads(view["match_reasons"]) if view["match_reasons"] else None
    view["unread"] = bool(row["unread"]) if "unread" in row.keys() else False
    if view["observed_at"]:
        view["source_observed_at"] = view["observed_at"]
    return view


JOB_WITH_UNREAD = """SELECT o.*, EXISTS (SELECT 1 FROM job_alerts a WHERE a.job_id=o.id AND a.read_at IS NULL) AS unread
FROM opportunities o"""
