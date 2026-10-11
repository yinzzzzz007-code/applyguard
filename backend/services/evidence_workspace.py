"""Local evidence workspace: SQLite index + gitignored file snapshots."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, urlparse

_DB_LOCK = threading.RLock()

from backend.services.evidence_parsers import (
    MAX_FILE_BYTES,
    conflict_between_claim_and_fields,
    extension_of,
    guess_media_type,
    is_allowed_path,
    is_hidden_path,
    parse_file,
)
from backend.services.local_store import local_dir

EXTRACTOR_VERSION = "1.0.0"
MAX_BATCH_FILES = 30


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def evidence_root() -> Path:
    override = os.getenv("APPLYGUARD_EVIDENCE_DIR", "").strip()
    root = Path(override) if override else local_dir() / "evidence"
    root.mkdir(parents=True, exist_ok=True)
    return root


def db_path() -> Path:
    return evidence_root() / "evidence.sqlite3"


def _connect() -> sqlite3.Connection:
    # timeout avoids "database is locked" kills under ThreadingHTTPServer
    conn = sqlite3.connect(str(db_path()), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    with _DB_LOCK:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db() -> None:
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspace (
              workspace_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_file (
              file_id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL,
              relative_path TEXT NOT NULL,
              media_type TEXT NOT NULL,
              size INTEGER NOT NULL,
              sha256 TEXT NOT NULL,
              imported_at TEXT NOT NULL,
              version INTEGER NOT NULL,
              state TEXT NOT NULL,
              parse_error TEXT,
              storage_name TEXT NOT NULL,
              preview_storage_name TEXT,
              is_conversion INTEGER NOT NULL DEFAULT 0,
              conversion_note TEXT,
              FOREIGN KEY (workspace_id) REFERENCES workspace(workspace_id) ON DELETE CASCADE
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_file_version
              ON source_file(workspace_id, relative_path, version);
            CREATE TABLE IF NOT EXISTS source_span (
              span_id TEXT PRIMARY KEY,
              file_id TEXT NOT NULL,
              page INTEGER,
              bbox_json TEXT,
              line_start INTEGER,
              line_end INTEGER,
              raw_text TEXT NOT NULL,
              extractor TEXT NOT NULL,
              extractor_version TEXT NOT NULL,
              FOREIGN KEY (file_id) REFERENCES source_file(file_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS evidence_record (
              evidence_id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL,
              kind TEXT NOT NULL,
              normalized_fields_json TEXT NOT NULL,
              ocr_fields_json TEXT,
              review_state TEXT NOT NULL,
              reviewed_at TEXT,
              primary_file_id TEXT,
              FOREIGN KEY (workspace_id) REFERENCES workspace(workspace_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS evidence_span (
              evidence_id TEXT NOT NULL,
              span_id TEXT NOT NULL,
              PRIMARY KEY (evidence_id, span_id),
              FOREIGN KEY (evidence_id) REFERENCES evidence_record(evidence_id) ON DELETE CASCADE,
              FOREIGN KEY (span_id) REFERENCES source_span(span_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS evidence_link (
              link_id TEXT PRIMARY KEY,
              target_type TEXT NOT NULL,
              target_id TEXT NOT NULL,
              evidence_id TEXT NOT NULL,
              file_sha256 TEXT NOT NULL,
              linked_at TEXT NOT NULL,
              link_state TEXT NOT NULL,
              FOREIGN KEY (evidence_id) REFERENCES evidence_record(evidence_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_span_text ON source_span(raw_text);
            CREATE INDEX IF NOT EXISTS idx_link_target ON evidence_link(target_type, target_id);
            """
        )


def _workspace_dir(workspace_id: str) -> Path:
    path = evidence_root() / workspace_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_workspace(name: str) -> dict[str, Any]:
    init_db()
    name = (name or "").strip() or "本地证据工作区"
    workspace_id = _new_id("ws")
    created = _utc_now()
    with _db() as conn:
        conn.execute(
            "INSERT INTO workspace(workspace_id, name, created_at) VALUES (?, ?, ?)",
            (workspace_id, name, created),
        )
    _workspace_dir(workspace_id)
    return {"workspace_id": workspace_id, "name": name, "created_at": created}


def list_workspaces() -> list[dict[str, Any]]:
    init_db()
    with _db() as conn:
        rows = conn.execute(
            "SELECT workspace_id, name, created_at FROM workspace ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_workspace(workspace_id: str) -> dict[str, Any] | None:
    init_db()
    with _db() as conn:
        row = conn.execute(
            "SELECT workspace_id, name, created_at FROM workspace WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_workspace(workspace_id: str) -> dict[str, Any]:
    init_db()
    ws = get_workspace(workspace_id)
    if not ws:
        raise ValueError("工作区不存在")
    with _db() as conn:
        links = conn.execute(
            """
            SELECT COUNT(*) AS n FROM evidence_link l
            JOIN evidence_record e ON e.evidence_id = l.evidence_id
            WHERE e.workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()["n"]
        conn.execute("DELETE FROM workspace WHERE workspace_id = ?", (workspace_id,))
    folder = evidence_root() / workspace_id
    if folder.is_dir():
        import shutil

        shutil.rmtree(folder, ignore_errors=True)
    return {
        "deleted": True,
        "workspace_id": workspace_id,
        "removed_links": links,
        "notice": "已删除本机工作区副本与索引。关联的 Claim/奖项将失去该来源。",
    }


def _file_row(conn: sqlite3.Connection, file_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM source_file WHERE file_id = ?", (file_id,)).fetchone()


def _serialize_file(row: sqlite3.Row, span_count: int | None = None) -> dict[str, Any]:
    payload = {
        "file_id": row["file_id"],
        "workspace_id": row["workspace_id"],
        "relative_path": row["relative_path"],
        "media_type": row["media_type"],
        "size": row["size"],
        "sha256": row["sha256"],
        "imported_at": row["imported_at"],
        "version": row["version"],
        "state": row["state"],
        "parse_error": row["parse_error"],
        "is_conversion": bool(row["is_conversion"]),
        "conversion_note": row["conversion_note"],
    }
    if span_count is not None:
        payload["span_count"] = span_count
    return payload


def _file_recognition_meta(conn: sqlite3.Connection, file_id: str) -> dict[str, Any]:
    """Attach evidence/OCR summary used by list + dedupe responses."""
    ev = conn.execute(
        """
        SELECT evidence_id, review_state, normalized_fields_json, ocr_fields_json
        FROM evidence_record
        WHERE primary_file_id = ?
        ORDER BY reviewed_at IS NULL, reviewed_at DESC
        LIMIT 1
        """,
        (file_id,),
    ).fetchone()
    preview_row = conn.execute(
        """
        SELECT GROUP_CONCAT(t.raw_text, ' ') AS preview
        FROM (
          SELECT raw_text FROM source_span
          WHERE file_id = ? AND TRIM(raw_text) != ''
          LIMIT 8
        ) AS t
        """,
        (file_id,),
    ).fetchone()
    fields = json.loads(ev["normalized_fields_json"] or "{}") if ev and ev["normalized_fields_json"] else {}
    ocr_fields = json.loads(ev["ocr_fields_json"] or "{}") if ev and ev["ocr_fields_json"] else {}
    preview = ((preview_row["preview"] if preview_row else None) or "").strip()
    return {
        "evidence_id": ev["evidence_id"] if ev else None,
        "evidence_review_state": ev["review_state"] if ev else None,
        "normalized_fields": fields,
        "ocr_fields": ocr_fields,
        "ocr_text_preview": preview[:160],
        "recognition_saved": bool(preview or any(str(v).strip() for v in fields.values())),
    }


def _should_reuse_existing(state: str, span_count: int, force_reparse: bool) -> bool:
    """Reuse prior OCR/parse when content unchanged and not explicitly forced."""
    if force_reparse:
        return False
    # Allow retry for failed/empty recognition without re-uploading different bytes
    if state in {"FAILED", "PARSING", "PENDING"}:
        return False
    if span_count > 0:
        return True
    return state in {"INDEXED", "NEEDS_REVIEW"}


def purge_hidden_path_files(workspace_id: str) -> int:
    """Remove previously imported files that live under `.`-prefixed path segments."""
    init_db()
    removed = 0
    with _db() as conn:
        rows = conn.execute(
            "SELECT file_id, relative_path, storage_name, preview_storage_name FROM source_file WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchall()
        ws_dir = _workspace_dir(workspace_id)
        for row in rows:
            if not is_hidden_path(str(row["relative_path"] or "")):
                continue
            file_id = row["file_id"]
            # Drop dependent rows first (SQLite may not enforce FK cascade)
            span_ids = [
                s["span_id"]
                for s in conn.execute(
                    "SELECT span_id FROM source_span WHERE file_id = ?",
                    (file_id,),
                ).fetchall()
            ]
            for span_id in span_ids:
                conn.execute("DELETE FROM evidence_span WHERE span_id = ?", (span_id,))
            conn.execute("DELETE FROM source_span WHERE file_id = ?", (file_id,))
            ev_rows = conn.execute(
                "SELECT evidence_id FROM evidence_record WHERE primary_file_id = ?",
                (file_id,),
            ).fetchall()
            for ev in ev_rows:
                conn.execute("DELETE FROM evidence_link WHERE evidence_id = ?", (ev["evidence_id"],))
                conn.execute("DELETE FROM evidence_span WHERE evidence_id = ?", (ev["evidence_id"],))
                conn.execute("DELETE FROM evidence_record WHERE evidence_id = ?", (ev["evidence_id"],))
            conn.execute("DELETE FROM source_file WHERE file_id = ?", (file_id,))
            for name in (row["storage_name"], row["preview_storage_name"]):
                if not name:
                    continue
                path = ws_dir / str(name)
                if path.is_file():
                    try:
                        path.unlink()
                    except OSError:
                        pass
            removed += 1
    return removed


def list_files(workspace_id: str) -> list[dict[str, Any]]:
    init_db()
    if not get_workspace(workspace_id):
        raise ValueError("工作区不存在")
    # Drop legacy imports that predate the hidden-folder skip rule
    purge_hidden_path_files(workspace_id)
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT f.*,
                   (SELECT COUNT(*) FROM source_span s WHERE s.file_id = f.file_id) AS span_count,
                   (
                     SELECT e.evidence_id FROM evidence_record e
                     WHERE e.primary_file_id = f.file_id
                     ORDER BY e.reviewed_at IS NULL, e.reviewed_at DESC
                     LIMIT 1
                   ) AS evidence_id,
                   (
                     SELECT e.review_state FROM evidence_record e
                     WHERE e.primary_file_id = f.file_id
                     ORDER BY e.reviewed_at IS NULL, e.reviewed_at DESC
                     LIMIT 1
                   ) AS evidence_review_state,
                   (
                     SELECT e.normalized_fields_json FROM evidence_record e
                     WHERE e.primary_file_id = f.file_id
                     ORDER BY e.reviewed_at IS NULL, e.reviewed_at DESC
                     LIMIT 1
                   ) AS normalized_fields_json,
                   (
                     SELECT e.ocr_fields_json FROM evidence_record e
                     WHERE e.primary_file_id = f.file_id
                     ORDER BY e.reviewed_at IS NULL, e.reviewed_at DESC
                     LIMIT 1
                   ) AS ocr_fields_json,
                   (
                     SELECT GROUP_CONCAT(t.raw_text, ' ')
                     FROM (
                       SELECT s.raw_text AS raw_text
                       FROM source_span s
                       WHERE s.file_id = f.file_id AND TRIM(s.raw_text) != ''
                       LIMIT 8
                     ) AS t
                   ) AS ocr_text_preview
            FROM source_file f
            WHERE f.workspace_id = ?
            ORDER BY f.relative_path ASC, f.version DESC
            """,
            (workspace_id,),
        ).fetchall()
    # Prefer latest version per path in listing
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = row["relative_path"]
        if key in seen:
            continue
        if is_hidden_path(str(key or "")):
            continue
        seen.add(key)
        item = _serialize_file(row, span_count=row["span_count"])
        fields = json.loads(row["normalized_fields_json"] or "{}") if row["normalized_fields_json"] else {}
        ocr_fields = json.loads(row["ocr_fields_json"] or "{}") if row["ocr_fields_json"] else {}
        preview = (row["ocr_text_preview"] or "").strip()
        item["evidence_id"] = row["evidence_id"]
        item["evidence_review_state"] = row["evidence_review_state"]
        item["normalized_fields"] = fields
        item["ocr_fields"] = ocr_fields
        item["ocr_text_preview"] = preview[:160]
        item["recognition_saved"] = bool(preview or any(str(v).strip() for v in fields.values()))
        out.append(item)
    return out


def get_file(file_id: str) -> dict[str, Any]:
    init_db()
    with _db() as conn:
        row = _file_row(conn, file_id)
        if not row:
            raise ValueError("文件不存在")
        spans = conn.execute(
            "SELECT * FROM source_span WHERE file_id = ? ORDER BY page ASC, line_start ASC",
            (file_id,),
        ).fetchall()
    return {
        **_serialize_file(row, span_count=len(spans)),
        "spans": [_serialize_span(s) for s in spans],
    }


def _serialize_span(row: sqlite3.Row) -> dict[str, Any]:
    bbox = json.loads(row["bbox_json"]) if row["bbox_json"] else None
    return {
        "span_id": row["span_id"],
        "file_id": row["file_id"],
        "page": row["page"],
        "bbox": bbox,
        "line_start": row["line_start"],
        "line_end": row["line_end"],
        "raw_text": row["raw_text"],
        "extractor": row["extractor"],
        "extractor_version": row["extractor_version"],
    }


def resolve_preview_path(file_id: str) -> tuple[Path, str]:
    init_db()
    with _db() as conn:
        row = _file_row(conn, file_id)
        if not row:
            raise ValueError("文件不存在")
        storage = row["preview_storage_name"] or row["storage_name"]
        media = "application/pdf" if row["preview_storage_name"] else row["media_type"]
        path = _workspace_dir(row["workspace_id"]) / storage
        # Path traversal guard: must stay inside workspace dir
        workspace_root = _workspace_dir(row["workspace_id"]).resolve()
        resolved = path.resolve()
        if not str(resolved).startswith(str(workspace_root)) or not resolved.is_file():
            raise ValueError("预览文件不可用或路径非法")
        return resolved, media


def import_files(workspace_id: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    init_db()
    if not get_workspace(workspace_id):
        raise ValueError("工作区不存在")
    if not isinstance(files, list) or not files:
        raise ValueError("files 必须为非空数组")
    if len(files) > MAX_BATCH_FILES:
        raise ValueError(f"单批最多导入 {MAX_BATCH_FILES} 个文件")

    # Map relative_path -> item for OCR sidecar companions (*.png.ocr.json)
    by_path = {
        str(item.get("relative_path") or "").replace("\\", "/").lstrip("/"): item
        for item in files
        if isinstance(item, dict)
    }
    results: list[dict[str, Any]] = []
    for item in files:
        rel = str(item.get("relative_path") or "").replace("\\", "/").lstrip("/")
        if rel.endswith(".ocr.json"):
            # Sidecars are consumed with their image; do not index as standalone evidence.
            results.append(
                {
                    "relative_path": rel,
                    "state": "INDEXED",
                    "parse_error": None,
                    "notice": "OCR 旁路文件，已随对应图片处理",
                    "sidecar": True,
                }
            )
            continue
        results.append(_import_one(workspace_id, item, companions=by_path))
    return {"workspace_id": workspace_id, "files": results}


def _import_one(
    workspace_id: str,
    item: dict[str, Any],
    companions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    relative_path = str(item.get("relative_path") or "").replace("\\", "/").lstrip("/")
    content_b64 = item.get("content_base64")
    if not relative_path or not isinstance(content_b64, str):
        return {
            "relative_path": relative_path or "(missing)",
            "state": "FAILED",
            "parse_error": "缺少 relative_path 或 content_base64",
        }
    if is_hidden_path(relative_path):
        return {
            "relative_path": relative_path,
            "state": "FAILED",
            "parse_error": "已跳过隐藏路径（. 开头的文件夹/文件）",
        }
    if not is_allowed_path(relative_path):
        return {
            "relative_path": relative_path,
            "state": "FAILED",
            "parse_error": f"不支持的路径或类型：{extension_of(relative_path) or '(无扩展名)'}",
        }
    try:
        raw = base64.b64decode(content_b64, validate=False)
    except Exception:  # noqa: BLE001
        return {"relative_path": relative_path, "state": "FAILED", "parse_error": "Base64 解码失败"}
    if not raw:
        return {"relative_path": relative_path, "state": "FAILED", "parse_error": "文件为空"}
    if len(raw) > MAX_FILE_BYTES:
        return {
            "relative_path": relative_path,
            "state": "FAILED",
            "parse_error": f"文件超过 {MAX_FILE_BYTES} 字节上限",
        }

    digest = hashlib.sha256(raw).hexdigest()
    force_reparse = bool(item.get("force_reparse"))
    ws_dir = _workspace_dir(workspace_id)
    stale_previous = False
    reparse_existing_id: str | None = None
    with _db() as conn:
        latest = conn.execute(
            """
            SELECT * FROM source_file
            WHERE workspace_id = ? AND relative_path = ?
            ORDER BY version DESC LIMIT 1
            """,
            (workspace_id, relative_path),
        ).fetchone()
        if latest and latest["sha256"] == digest:
            spans = conn.execute(
                "SELECT COUNT(*) AS n FROM source_span WHERE file_id = ?",
                (latest["file_id"],),
            ).fetchone()["n"]
            if _should_reuse_existing(str(latest["state"] or ""), int(spans or 0), force_reparse):
                return {
                    **_serialize_file(latest, span_count=spans),
                    **_file_recognition_meta(conn, latest["file_id"]),
                    "deduplicated": True,
                    "skipped_reparse": True,
                    "notice": "内容未变，复用已有识别结果（未重跑 OCR）",
                }
            # Same bytes but previous parse failed / forced → reparse in place after txn
            reparse_existing_id = latest["file_id"]
            existing_storage = latest["storage_name"]
        else:
            version = (latest["version"] + 1) if latest else 1
            stale_previous = bool(latest)
            file_id = _new_id("file")
            storage_name = f"v{version}_{digest[:16]}_{Path(relative_path).name}"
            dest = ws_dir / storage_name
            dest.write_bytes(raw)
            _write_ocr_sidecar(dest, relative_path, companions or {}, item)

            # Mark older active links STALE when content changes
            if latest:
                conn.execute(
                    """
                    UPDATE evidence_link
                    SET link_state = 'STALE'
                    WHERE file_sha256 = ? AND link_state = 'ACTIVE'
                    """,
                    (latest["sha256"],),
                )
                conn.execute(
                    """
                    UPDATE evidence_record
                    SET review_state = 'STALE'
                    WHERE primary_file_id = ? AND review_state = 'REVIEWED'
                    """,
                    (latest["file_id"],),
                )

            conn.execute(
                """
                INSERT INTO source_file(
                  file_id, workspace_id, relative_path, media_type, size, sha256,
                  imported_at, version, state, parse_error, storage_name,
                  preview_storage_name, is_conversion, conversion_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PARSING', NULL, ?, NULL, 0, NULL)
                """,
                (
                    file_id,
                    workspace_id,
                    relative_path,
                    guess_media_type(relative_path),
                    len(raw),
                    digest,
                    _utc_now(),
                    version,
                    storage_name,
                ),
            )

    if reparse_existing_id:
        existing_dest = ws_dir / existing_storage
        _write_ocr_sidecar(existing_dest, relative_path, companions or {}, item)
        return reparse_file(reparse_existing_id)

    parsed = parse_file(dest, relative_path, ws_dir)
    preview_storage = None
    if parsed.preview_path and parsed.preview_path.is_file():
        preview_storage = f"preview_{storage_name}.pdf"
        preview_dest = ws_dir / preview_storage
        preview_dest.write_bytes(parsed.preview_path.read_bytes())

    with _db() as conn:
        span_ids: list[str] = []
        for draft in parsed.spans:
            span_id = _new_id("span")
            span_ids.append(span_id)
            conn.execute(
                """
                INSERT INTO source_span(
                  span_id, file_id, page, bbox_json, line_start, line_end,
                  raw_text, extractor, extractor_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    span_id,
                    file_id,
                    draft.page,
                    json.dumps(draft.bbox) if draft.bbox else None,
                    draft.line_start,
                    draft.line_end,
                    draft.raw_text,
                    draft.extractor,
                    EXTRACTOR_VERSION,
                ),
            )
        # Draft evidence record awaiting human review
        evidence_id = _new_id("evloc")
        conn.execute(
            """
            INSERT INTO evidence_record(
              evidence_id, workspace_id, kind, normalized_fields_json, ocr_fields_json,
              review_state, reviewed_at, primary_file_id
            ) VALUES (?, ?, 'AWARD_CERTIFICATE', ?, ?, 'UNREVIEWED', NULL, ?)
            """,
            (
                evidence_id,
                workspace_id,
                json.dumps(parsed.suggested_fields, ensure_ascii=False),
                json.dumps(parsed.suggested_fields, ensure_ascii=False),
                file_id,
            ),
        )
        for span_id in span_ids:
            conn.execute(
                "INSERT INTO evidence_span(evidence_id, span_id) VALUES (?, ?)",
                (evidence_id, span_id),
            )
        conn.execute(
            """
            UPDATE source_file
            SET state = ?, parse_error = ?, media_type = ?, is_conversion = ?,
                conversion_note = ?, preview_storage_name = ?
            WHERE file_id = ?
            """,
            (
                parsed.state,
                parsed.error,
                parsed.media_type or guess_media_type(relative_path),
                1 if parsed.is_conversion else 0,
                parsed.conversion_note,
                preview_storage,
                file_id,
            ),
        )
        row = _file_row(conn, file_id)
    assert row is not None
    return {
        **_serialize_file(row, span_count=len(parsed.spans)),
        "evidence_id": evidence_id,
        "suggested_fields": parsed.suggested_fields,
        "deduplicated": False,
        "stale_previous": stale_previous,
    }


def reparse_file(file_id: str) -> dict[str, Any]:
    """Re-run OCR/parse on an already stored file without re-uploading bytes."""
    init_db()
    with _db() as conn:
        row = _file_row(conn, file_id)
        if not row:
            raise ValueError("文件不存在")
        workspace_id = row["workspace_id"]
        relative_path = row["relative_path"]
        storage_name = row["storage_name"]
        ws_dir = _workspace_dir(workspace_id)
        dest = ws_dir / storage_name
        if not dest.is_file():
            raise ValueError("存储文件丢失，请重新导入")
        conn.execute(
            "UPDATE source_file SET state = 'PARSING', parse_error = NULL WHERE file_id = ?",
            (file_id,),
        )
        # Drop old spans (evidence_span cascades via FK on span delete if enabled;
        # SQLite needs explicit cleanup for join table when CASCADE may be off).
        old_spans = conn.execute(
            "SELECT span_id FROM source_span WHERE file_id = ?",
            (file_id,),
        ).fetchall()
        for s in old_spans:
            conn.execute("DELETE FROM evidence_span WHERE span_id = ?", (s["span_id"],))
        conn.execute("DELETE FROM source_span WHERE file_id = ?", (file_id,))
        ev = conn.execute(
            """
            SELECT evidence_id, review_state FROM evidence_record
            WHERE primary_file_id = ?
            ORDER BY reviewed_at IS NULL, reviewed_at DESC LIMIT 1
            """,
            (file_id,),
        ).fetchone()

    parsed = parse_file(dest, relative_path, ws_dir)
    preview_storage = None
    if parsed.preview_path and parsed.preview_path.is_file():
        preview_storage = f"preview_{storage_name}.pdf"
        preview_dest = ws_dir / preview_storage
        preview_dest.write_bytes(parsed.preview_path.read_bytes())

    with _db() as conn:
        span_ids: list[str] = []
        for draft in parsed.spans:
            span_id = _new_id("span")
            span_ids.append(span_id)
            conn.execute(
                """
                INSERT INTO source_span(
                  span_id, file_id, page, bbox_json, line_start, line_end,
                  raw_text, extractor, extractor_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    span_id,
                    file_id,
                    draft.page,
                    json.dumps(draft.bbox) if draft.bbox else None,
                    draft.line_start,
                    draft.line_end,
                    draft.raw_text,
                    draft.extractor,
                    EXTRACTOR_VERSION,
                ),
            )
        evidence_id = ev["evidence_id"] if ev else _new_id("evloc")
        if ev:
            # Always refresh OCR fields; keep human-confirmed normalized fields if REVIEWED
            if str(ev["review_state"] or "") == "REVIEWED":
                conn.execute(
                    """
                    UPDATE evidence_record
                    SET ocr_fields_json = ?
                    WHERE evidence_id = ?
                    """,
                    (json.dumps(parsed.suggested_fields, ensure_ascii=False), evidence_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE evidence_record
                    SET ocr_fields_json = ?, normalized_fields_json = ?, review_state = 'UNREVIEWED'
                    WHERE evidence_id = ?
                    """,
                    (
                        json.dumps(parsed.suggested_fields, ensure_ascii=False),
                        json.dumps(parsed.suggested_fields, ensure_ascii=False),
                        evidence_id,
                    ),
                )
        else:
            conn.execute(
                """
                INSERT INTO evidence_record(
                  evidence_id, workspace_id, kind, normalized_fields_json, ocr_fields_json,
                  review_state, reviewed_at, primary_file_id
                ) VALUES (?, ?, 'AWARD_CERTIFICATE', ?, ?, 'UNREVIEWED', NULL, ?)
                """,
                (
                    evidence_id,
                    workspace_id,
                    json.dumps(parsed.suggested_fields, ensure_ascii=False),
                    json.dumps(parsed.suggested_fields, ensure_ascii=False),
                    file_id,
                ),
            )
        for span_id in span_ids:
            conn.execute(
                "INSERT INTO evidence_span(evidence_id, span_id) VALUES (?, ?)",
                (evidence_id, span_id),
            )
        conn.execute(
            """
            UPDATE source_file
            SET state = ?, parse_error = ?, media_type = ?, is_conversion = ?,
                conversion_note = ?, preview_storage_name = COALESCE(?, preview_storage_name)
            WHERE file_id = ?
            """,
            (
                parsed.state,
                parsed.error,
                parsed.media_type or guess_media_type(relative_path),
                1 if parsed.is_conversion else 0,
                parsed.conversion_note,
                preview_storage,
                file_id,
            ),
        )
        row = _file_row(conn, file_id)
        assert row is not None
        return {
            **_serialize_file(row, span_count=len(parsed.spans)),
            **_file_recognition_meta(conn, file_id),
            "evidence_id": evidence_id,
            "suggested_fields": parsed.suggested_fields,
            "deduplicated": True,
            "reparsed": True,
            "notice": "已基于本机原件重新识别（未重新上传）",
        }


def _write_ocr_sidecar(
    dest: Path,
    relative_path: str,
    companions: dict[str, dict[str, Any]],
    item: dict[str, Any],
) -> None:
    """Place OCR sidecar next to stored image so parsers can find it."""
    candidates = [
        f"{relative_path}.ocr.json",
        str(Path(relative_path).name) + ".ocr.json",
    ]
    payload_b64 = item.get("ocr_sidecar_base64")
    raw_side: bytes | None = None
    if isinstance(payload_b64, str) and payload_b64:
        try:
            raw_side = base64.b64decode(payload_b64, validate=False)
        except Exception:  # noqa: BLE001
            raw_side = None
    if raw_side is None:
        for key in candidates:
            companion = companions.get(key)
            if not companion:
                continue
            b64 = companion.get("content_base64")
            if isinstance(b64, str):
                try:
                    raw_side = base64.b64decode(b64, validate=False)
                    break
                except Exception:  # noqa: BLE001
                    continue
    if raw_side:
        (dest.parent / f"{dest.name}.ocr.json").write_bytes(raw_side)


def search_evidence(query: str, workspace_id: str | None = None, limit: int = 20) -> dict[str, Any]:
    init_db()
    q = (query or "").strip()
    if not q:
        raise ValueError("q 不能为空")
    limit = max(1, min(int(limit), 50))
    like = f"%{q}%"
    sql = """
        SELECT s.*, f.relative_path, f.sha256, f.version, f.media_type, f.workspace_id,
               e.evidence_id, e.review_state, e.normalized_fields_json
        FROM source_span s
        JOIN source_file f ON f.file_id = s.file_id
        LEFT JOIN evidence_span es ON es.span_id = s.span_id
        LEFT JOIN evidence_record e ON e.evidence_id = es.evidence_id
        WHERE s.raw_text LIKE ?
    """
    params: list[Any] = [like]
    if workspace_id:
        sql += " AND f.workspace_id = ?"
        params.append(workspace_id)
    sql += " ORDER BY e.review_state = 'REVIEWED' DESC, f.version DESC LIMIT ?"
    params.append(limit)
    with _db() as conn:
        rows = conn.execute(sql, params).fetchall()
    matches = []
    for row in rows:
        fields = json.loads(row["normalized_fields_json"] or "{}") if row["normalized_fields_json"] else {}
        matches.append(
            {
                "span": _serialize_span(row),
                "file_id": row["file_id"],
                "relative_path": row["relative_path"],
                "sha256": row["sha256"],
                "version": row["version"],
                "media_type": row["media_type"],
                "workspace_id": row["workspace_id"],
                "evidence_id": row["evidence_id"],
                "review_state": row["review_state"],
                "normalized_fields": fields,
                "relevance_note": "可能相关（关键词命中），需人工确认",
            }
        )
    return {"query": q, "matches": matches}


def get_evidence(evidence_id: str) -> dict[str, Any]:
    init_db()
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM evidence_record WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
        if not row:
            raise ValueError("证据不存在")
        span_rows = conn.execute(
            """
            SELECT s.* FROM source_span s
            JOIN evidence_span es ON es.span_id = s.span_id
            WHERE es.evidence_id = ?
            """,
            (evidence_id,),
        ).fetchall()
        file_payload = None
        if row["primary_file_id"]:
            frow = _file_row(conn, row["primary_file_id"])
            if frow:
                file_payload = _serialize_file(frow)
        links = conn.execute(
            "SELECT * FROM evidence_link WHERE evidence_id = ? ORDER BY linked_at DESC",
            (evidence_id,),
        ).fetchall()
    return {
        "evidence_id": row["evidence_id"],
        "workspace_id": row["workspace_id"],
        "kind": row["kind"],
        "normalized_fields": json.loads(row["normalized_fields_json"] or "{}"),
        "ocr_fields": json.loads(row["ocr_fields_json"] or "{}") if row["ocr_fields_json"] else {},
        "review_state": row["review_state"],
        "reviewed_at": row["reviewed_at"],
        "primary_file_id": row["primary_file_id"],
        "file": file_payload,
        "spans": [_serialize_span(s) for s in span_rows],
        "links": [dict(l) for l in links],
    }


def review_evidence(evidence_id: str, body: dict[str, Any]) -> dict[str, Any]:
    init_db()
    fields = body.get("normalized_fields")
    if not isinstance(fields, dict):
        raise ValueError("normalized_fields 必须为对象")
    cleaned = {
        "recipient": str(fields.get("recipient") or "").strip(),
        "award_name": str(fields.get("award_name") or "").strip(),
        "grade": str(fields.get("grade") or "").strip(),
        "issuer": str(fields.get("issuer") or "").strip(),
        "date": str(fields.get("date") or "").strip(),
    }
    review_state = str(body.get("review_state") or "REVIEWED").upper()
    if review_state not in {"REVIEWED", "CONFLICT", "UNREVIEWED"}:
        raise ValueError("review_state 无效")
    span_ids = body.get("span_ids")
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM evidence_record WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
        if not row:
            raise ValueError("证据不存在")
        # Preserve reviewed_at when only saving a draft (UNREVIEWED); set on confirm.
        if review_state == "REVIEWED":
            reviewed_at = _utc_now()
            conn.execute(
                """
                UPDATE evidence_record
                SET normalized_fields_json = ?, review_state = ?, reviewed_at = ?
                WHERE evidence_id = ?
                """,
                (json.dumps(cleaned, ensure_ascii=False), review_state, reviewed_at, evidence_id),
            )
        else:
            # Draft save: keep OCR originals, persist corrected fields without clearing history
            conn.execute(
                """
                UPDATE evidence_record
                SET normalized_fields_json = ?, review_state = ?
                WHERE evidence_id = ?
                """,
                (json.dumps(cleaned, ensure_ascii=False), review_state, evidence_id),
            )
        if isinstance(span_ids, list):
            conn.execute("DELETE FROM evidence_span WHERE evidence_id = ?", (evidence_id,))
            for span_id in span_ids:
                if isinstance(span_id, str) and span_id:
                    conn.execute(
                        "INSERT OR IGNORE INTO evidence_span(evidence_id, span_id) VALUES (?, ?)",
                        (evidence_id, span_id),
                    )
        if row["primary_file_id"] and review_state == "REVIEWED":
            conn.execute(
                "UPDATE source_file SET state = 'INDEXED', parse_error = NULL WHERE file_id = ?",
                (row["primary_file_id"],),
            )
    return get_evidence(evidence_id)


def create_link(body: dict[str, Any]) -> dict[str, Any]:
    init_db()
    target_type = str(body.get("target_type") or "").strip()
    target_id = str(body.get("target_id") or "").strip()
    evidence_id = str(body.get("evidence_id") or "").strip()
    link_state = str(body.get("link_state") or "ACTIVE").strip().upper()
    if target_type not in {"award", "experience", "project", "internship", "claim", "metric"}:
        raise ValueError("target_type 必须是 award / experience / project / internship / claim / metric")
    if link_state not in {"ACTIVE", "REJECTED"}:
        raise ValueError("link_state 必须是 ACTIVE 或 REJECTED")
    if not target_id or not evidence_id:
        raise ValueError("target_id 与 evidence_id 必填")
    with _db() as conn:
        ev = conn.execute(
            "SELECT * FROM evidence_record WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
        if not ev:
            raise ValueError("证据不存在")
        if link_state == "ACTIVE" and ev["review_state"] != "REVIEWED":
            raise ValueError("仅已核对证据可关联；请先完成人工确认")
        file_sha = ""
        if ev["primary_file_id"]:
            frow = _file_row(conn, ev["primary_file_id"])
            if frow:
                file_sha = frow["sha256"]
        # Replace prior decision for the same target + evidence
        conn.execute(
            """
            DELETE FROM evidence_link
            WHERE target_type = ? AND target_id = ? AND evidence_id = ?
            """,
            (target_type, target_id, evidence_id),
        )
        link_id = _new_id("link")
        linked_at = _utc_now()
        conn.execute(
            """
            INSERT INTO evidence_link(
              link_id, target_type, target_id, evidence_id, file_sha256, linked_at, link_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (link_id, target_type, target_id, evidence_id, file_sha, linked_at, link_state),
        )
    return {
        "link_id": link_id,
        "target_type": target_type,
        "target_id": target_id,
        "evidence_id": evidence_id,
        "file_sha256": file_sha,
        "linked_at": linked_at,
        "link_state": link_state,
    }


def remove_link(body: dict[str, Any]) -> dict[str, Any]:
    """Remove an ACTIVE/REJECTED link by link_id or target+evidence."""
    init_db()
    link_id = str(body.get("link_id") or "").strip()
    target_type = str(body.get("target_type") or "").strip()
    target_id = str(body.get("target_id") or "").strip()
    evidence_id = str(body.get("evidence_id") or "").strip()
    with _db() as conn:
        if link_id:
            cur = conn.execute("DELETE FROM evidence_link WHERE link_id = ?", (link_id,))
            removed = cur.rowcount
        elif target_type and target_id:
            if evidence_id:
                cur = conn.execute(
                    """
                    DELETE FROM evidence_link
                    WHERE target_type = ? AND target_id = ? AND evidence_id = ?
                    """,
                    (target_type, target_id, evidence_id),
                )
            else:
                cur = conn.execute(
                    """
                    DELETE FROM evidence_link
                    WHERE target_type = ? AND target_id = ?
                    """,
                    (target_type, target_id),
                )
            removed = cur.rowcount
        else:
            raise ValueError("需要 link_id，或 target_type + target_id")
    if removed <= 0:
        raise ValueError("未找到可删除的关联")
    return {"deleted": True, "removed": removed}


def list_links(target_type: str | None = None, target_id: str | None = None, evidence_id: str | None = None) -> dict[str, Any]:
    init_db()
    clauses: list[str] = []
    params: list[Any] = []
    if target_type:
        clauses.append("l.target_type = ?")
        params.append(target_type)
    if target_id:
        clauses.append("l.target_id = ?")
        params.append(target_id)
    if evidence_id:
        clauses.append("l.evidence_id = ?")
        params.append(evidence_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _db() as conn:
        rows = conn.execute(
            f"""
            SELECT l.*, e.review_state, e.normalized_fields_json, e.primary_file_id,
                   f.relative_path, f.version, f.state AS file_state, f.sha256 AS current_sha
            FROM evidence_link l
            JOIN evidence_record e ON e.evidence_id = l.evidence_id
            LEFT JOIN source_file f ON f.file_id = e.primary_file_id
            {where}
            ORDER BY l.linked_at DESC
            """,
            params,
        ).fetchall()
        # Refresh STALE if linked sha no longer matches current file sha
        out = []
        for row in rows:
            link_state = row["link_state"]
            if row["current_sha"] and row["file_sha256"] and row["current_sha"] != row["file_sha256"]:
                link_state = "STALE"
                if row["link_state"] != "STALE":
                    conn.execute(
                        "UPDATE evidence_link SET link_state = 'STALE' WHERE link_id = ?",
                        (row["link_id"],),
                    )
            item = dict(row)
            item["link_state"] = link_state
            item["normalized_fields"] = json.loads(row["normalized_fields_json"] or "{}")
            del item["normalized_fields_json"]
            out.append(item)
    return {"links": out}


def check_claim_support(claim_text: str, evidence_id: str) -> dict[str, Any]:
    init_db()
    evidence = get_evidence(evidence_id)
    fields = evidence.get("normalized_fields") or {}
    reasons = conflict_between_claim_and_fields(claim_text, fields)
    link_state = "ACTIVE"
    with _db() as conn:
        link = conn.execute(
            "SELECT link_state FROM evidence_link WHERE evidence_id = ? ORDER BY linked_at DESC LIMIT 1",
            (evidence_id,),
        ).fetchone()
        if link:
            link_state = link["link_state"]
    if evidence["review_state"] == "STALE" or link_state == "STALE":
        return {
            "evidence_id": evidence_id,
            "status": "STALE",
            "supported": False,
            "reasons": ["证据文件已变更或关联已过期，需重新核对"],
            "evidence": evidence,
        }
    if evidence["review_state"] != "REVIEWED":
        return {
            "evidence_id": evidence_id,
            "status": "NEEDS_REVIEW",
            "supported": False,
            "reasons": ["证据尚未人工核对"],
            "evidence": evidence,
        }
    if reasons:
        return {
            "evidence_id": evidence_id,
            "status": "CONFLICT",
            "supported": False,
            "reasons": reasons,
            "evidence": evidence,
        }
    return {
        "evidence_id": evidence_id,
        "status": "VERIFIED",
        "supported": True,
        "reasons": [],
        "evidence": evidence,
        "notice": "相对本地已核对证据可支持该表述；不等于外部真伪鉴定。",
    }


def list_workspace_evidence(workspace_id: str) -> list[dict[str, Any]]:
    init_db()
    if not get_workspace(workspace_id):
        raise ValueError("工作区不存在")
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT evidence_id, kind, review_state, reviewed_at, primary_file_id,
                   normalized_fields_json
            FROM evidence_record
            WHERE workspace_id = ?
            ORDER BY reviewed_at IS NULL, reviewed_at DESC
            """,
            (workspace_id,),
        ).fetchall()
    out = []
    for row in rows:
        out.append(
            {
                "evidence_id": row["evidence_id"],
                "kind": row["kind"],
                "review_state": row["review_state"],
                "reviewed_at": row["reviewed_at"],
                "primary_file_id": row["primary_file_id"],
                "normalized_fields": json.loads(row["normalized_fields_json"] or "{}"),
            }
        )
    return out


_TOKEN_SPLIT = re.compile(r"[\s,，、;；:：/|（）()【】\[\]「」『』《》<>·•\-_|]+")
_NOISE_TOKENS = {
    "虚构",
    "示例",
    "演示",
    "的",
    "与",
    "和",
    "及",
    "了",
    "在",
    "等",
    "个人赛",
    "题目",
    "覆盖",
}


def _tokens(text: str) -> set[str]:
    parts = [p.strip().lower() for p in _TOKEN_SPLIT.split(text or "") if p.strip()]
    out: set[str] = set()
    for part in parts:
        if part in _NOISE_TOKENS or len(part) < 2:
            continue
        out.add(part)
        # keep meaningful 2+ char chinese chunks already split; also keep longer phrases
        if len(part) >= 4:
            out.add(part[:4])
    return out


def _award_blob(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(k) or "")
        for k in ("name", "issuer", "date", "description", "text", "title")
    )


def _experience_blob(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(k) or "")
        for k in (
            "organization",
            "title",
            "role",
            "description",
            "summary",
            "name",
            "start",
            "end",
            "start_date",
            "end_date",
        )
    )


def _collect_vault_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Build match targets from 经历库：实习 / 项目 / 获奖."""
    items: list[dict[str, Any]] = []

    def add_experience(raw: dict[str, Any], target_type: str, kind_label: str) -> None:
        exp_id = str(raw.get("experience_id") or raw.get("id") or "").strip()
        org = str(raw.get("organization") or "").strip()
        title = str(raw.get("title") or raw.get("role") or "").strip()
        if not exp_id or (not org and not title):
            return
        label = " · ".join(p for p in (org, title) if p)
        items.append(
            {
                "target_type": target_type,
                "target_id": exp_id,
                "kind": kind_label,
                "label": label,
                "text": _experience_blob(raw),
            }
        )

    for raw in body.get("internships") or []:
        if isinstance(raw, dict):
            add_experience(raw, "internship", "实习")
    for raw in body.get("projects") or []:
        if isinstance(raw, dict):
            add_experience(raw, "project", "项目")
    # Backward-compatible: generic experiences list
    for raw in body.get("experiences") or []:
        if isinstance(raw, dict):
            add_experience(raw, "experience", "经历")

    for award in body.get("awards") or []:
        if not isinstance(award, dict):
            continue
        award_id = str(award.get("award_id") or award.get("id") or "").strip()
        name = str(award.get("name") or "").strip()
        if not award_id or not name:
            continue
        items.append(
            {
                "target_type": "award",
                "target_id": award_id,
                "kind": "获奖/竞赛",
                "label": name,
                "text": _award_blob(award),
            }
        )
    for claim in body.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or claim.get("id") or "").strip()
        text = str(claim.get("text") or "").strip()
        if not claim_id or not text:
            continue
        items.append(
            {
                "target_type": "claim",
                "target_id": claim_id,
                "kind": "陈述",
                "label": text[:40] + ("…" if len(text) > 40 else ""),
                "text": text,
            }
        )
    return items


def _score_item_against_evidence(
    item_text: str,
    fields: dict[str, Any],
    corpus: str,
    review_state: str,
) -> tuple[int, list[str], list[str]]:
    """Return (score 0-100, match notes, conflict reasons)."""
    from backend.services.evidence_parsers import _GRADE, conflict_between_claim_and_fields

    notes: list[str] = []
    conflicts = conflict_between_claim_and_fields(item_text, fields)

    item_tokens = _tokens(item_text)
    field_text = " ".join(str(v) for v in fields.values() if v)
    evidence_tokens = _tokens(field_text + " " + corpus)
    if not item_tokens:
        return 0, notes, conflicts

    overlap = item_tokens & evidence_tokens
    score = min(70, int(100 * len(overlap) / max(3, len(item_tokens))))
    if overlap:
        notes.append("关键词重合：" + "、".join(sorted(overlap)[:6]))

    item_grade = _GRADE.search(item_text)
    ev_grade = str(fields.get("grade") or "")
    if not ev_grade:
        m = _GRADE.search(corpus)
        if m:
            ev_grade = m.group(1)
    if item_grade and ev_grade and item_grade.group(1) == ev_grade:
        score += 20
        notes.append(f"等级一致：{ev_grade}")
    elif item_grade and (item_grade.group(1) in corpus or item_grade.group(1) in field_text):
        score += 15
        notes.append(f"原文含等级：{item_grade.group(1)}")

    award_name = str(fields.get("award_name") or "")
    if award_name and award_name in item_text:
        score += 15
        notes.append(f"奖项名命中：{award_name}")
    # Soft name overlap: 程序设计 / 奖学金 etc.
    for token in item_tokens:
        if len(token) >= 2 and token in (field_text + corpus):
            score += 3
    score = min(100, score)

    issuer = str(fields.get("issuer") or "")
    if issuer and any(tok in issuer for tok in item_tokens if len(tok) >= 2):
        score += 8
        notes.append("颁发方相关")

    evidence_blob = field_text + " " + corpus
    # Type gate: 奖学金 vs 竞赛 must not cross-match on shared school tokens alone
    for marker in ("奖学金", "竞赛", "比赛", "大赛"):
        in_item = marker in item_text
        in_ev = marker in evidence_blob
        if in_item and in_ev:
            score += 12
            notes.append(f"类型一致：{marker}")
        elif in_item and not in_ev:
            score = max(0, score - 45)
            notes.append(f"类型不符：简历含「{marker}」，证据未见")

    if review_state == "REVIEWED":
        score += 5
        notes.append("证据已人工核对")
    elif review_state == "STALE":
        score = max(0, score - 30)
        notes.append("证据已过期，需重新核对")

    return min(100, score), notes, conflicts


def match_resume(workspace_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """
    Compare 经历库 entries (internship / project / award) against local evidence.
    Statuses: LINKED | MATCHED | NEEDS_CONFIRM | CONFLICT | MISSING | REJECTED
    """
    init_db()
    if not get_workspace(workspace_id):
        raise ValueError("工作区不存在")

    items = _collect_vault_items(body)
    if not items:
        raise ValueError("请提供经历库条目：internships / projects / awards（或 experiences / claims）")

    with _db() as conn:
        ev_rows = conn.execute(
            """
            SELECT e.*, f.relative_path, f.version, f.sha256, f.state AS file_state
            FROM evidence_record e
            LEFT JOIN source_file f ON f.file_id = e.primary_file_id
            WHERE e.workspace_id = ?
            """,
            (workspace_id,),
        ).fetchall()
        span_map: dict[str, str] = {}
        for row in conn.execute(
            """
            SELECT es.evidence_id, GROUP_CONCAT(s.raw_text, '\n') AS corpus
            FROM evidence_span es
            JOIN source_span s ON s.span_id = es.span_id
            JOIN evidence_record e ON e.evidence_id = es.evidence_id
            WHERE e.workspace_id = ?
            GROUP BY es.evidence_id
            """,
            (workspace_id,),
        ).fetchall():
            span_map[row["evidence_id"]] = row["corpus"] or ""

        link_rows = conn.execute(
            """
            SELECT l.* FROM evidence_link l
            JOIN evidence_record e ON e.evidence_id = l.evidence_id
            WHERE e.workspace_id = ?
            """,
            (workspace_id,),
        ).fetchall()

    links_by_target: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for link in link_rows:
        key = (link["target_type"], link["target_id"])
        links_by_target.setdefault(key, []).append(link)

    evidence_cards = []
    for row in ev_rows:
        fields = json.loads(row["normalized_fields_json"] or "{}")
        evidence_cards.append(
            {
                "evidence_id": row["evidence_id"],
                "review_state": row["review_state"],
                "fields": fields,
                "corpus": span_map.get(row["evidence_id"], ""),
                "relative_path": row["relative_path"],
                "version": row["version"],
                "primary_file_id": row["primary_file_id"],
                "file_sha256": row["sha256"],
            }
        )

    results = []
    summary = {
        "LINKED": 0,
        "MATCHED": 0,
        "NEEDS_CONFIRM": 0,
        "CONFLICT": 0,
        "MISSING": 0,
        "REJECTED": 0,
    }

    for item in items:
        key = (item["target_type"], item["target_id"])
        existing = links_by_target.get(key) or []
        active = [l for l in existing if l["link_state"] == "ACTIVE"]
        stale = [l for l in existing if l["link_state"] == "STALE"]
        rejected_ids = {l["evidence_id"] for l in existing if l["link_state"] == "REJECTED"}

        def _row(
            status: str,
            *,
            evidence_id: str | None,
            score: int,
            notes: list[str],
            action: str,
            relative_path: str | None = None,
            review_state: str | None = None,
            candidate_fields: dict[str, Any] | None = None,
            gap_hint: str | None = None,
        ) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "target_type": item["target_type"],
                "target_id": item["target_id"],
                "kind": item.get("kind") or item["target_type"],
                "label": item["label"],
                "status": status,
                "score": score,
                "evidence_id": evidence_id,
                "relative_path": relative_path,
                "review_state": review_state,
                "notes": notes,
                "action": action,
                "candidate_fields": candidate_fields or {},
            }
            if gap_hint:
                payload["gap_hint"] = gap_hint
            return payload

        if active:
            link = active[0]
            ev = next((e for e in evidence_cards if e["evidence_id"] == link["evidence_id"]), None)
            conflicts: list[str] = []
            if ev:
                _, _, conflicts = _score_item_against_evidence(
                    item["text"], ev["fields"], ev["corpus"], ev["review_state"]
                )
            if conflicts:
                status = "CONFLICT"
                action = "核对冲突：经历库表述与已关联证据不一致，请改经历库或更换证据"
            else:
                status = "LINKED"
                action = "已关联本地证据，可打开预览回看原件"
            results.append(
                _row(
                    status,
                    evidence_id=link["evidence_id"],
                    score=100 if status == "LINKED" else 40,
                    notes=conflicts or ["存在 ACTIVE 关联"],
                    action=action,
                    relative_path=ev["relative_path"] if ev else None,
                    review_state=ev["review_state"] if ev else None,
                    candidate_fields=ev["fields"] if ev else {},
                )
            )
            summary[status] += 1
            continue

        ranked: list[tuple[int, dict[str, Any], list[str], list[str]]] = []
        for ev in evidence_cards:
            if ev["evidence_id"] in rejected_ids:
                continue
            score, notes, conflicts = _score_item_against_evidence(
                item["text"], ev["fields"], ev["corpus"], ev["review_state"]
            )
            ranked.append((score, ev, notes, conflicts))
        ranked.sort(key=lambda x: x[0], reverse=True)
        best = ranked[0] if ranked else None

        if best and best[3] and best[0] >= 40:
            score, ev, notes, conflicts = best
            results.append(
                _row(
                    "CONFLICT",
                    evidence_id=ev["evidence_id"],
                    score=score,
                    notes=conflicts + notes,
                    action="候选可能冲突：可标为「不符合」或核对后关联",
                    relative_path=ev["relative_path"],
                    review_state=ev["review_state"],
                    candidate_fields=ev["fields"],
                )
            )
            summary["CONFLICT"] += 1
            continue

        if best and best[0] >= 45:
            score, ev, notes, conflicts = best
            if ev["review_state"] == "REVIEWED" and score >= 70:
                status = "MATCHED"
                action = "候选匹配度较高：可「确认关联」，若不对请标「不符合」"
            else:
                status = "NEEDS_CONFIRM"
                action = "找到可能相关材料：请预览后选择「确认关联」或「不符合」"
            if stale:
                notes = ["存在过期关联，建议用新版本重新确认", *notes]
            if rejected_ids:
                notes = [f"已排除 {len(rejected_ids)} 个标为不符合的候选", *notes]
            results.append(
                _row(
                    status,
                    evidence_id=ev["evidence_id"],
                    score=score,
                    notes=notes,
                    action=action,
                    relative_path=ev["relative_path"],
                    review_state=ev["review_state"],
                    candidate_fields=ev["fields"],
                )
            )
            summary[status] += 1
            continue

        hint_bits = [f"{item.get('kind', '')} {item['label']}".strip()]
        from backend.services.evidence_parsers import _GRADE

        g = _GRADE.search(item["text"])
        if g:
            hint_bits.append(f"需含「{g.group(1)}」")
        notes = ["工作区中未找到足够相关的原文"]
        if rejected_ids:
            notes.append(f"已排除 {len(rejected_ids)} 个不符合候选")
        results.append(
            _row(
                "MISSING",
                evidence_id=None,
                score=0,
                notes=notes,
                action="需要补充材料：请把对应证明放入文件夹后重新导入并对照经历库",
                gap_hint="、".join(hint_bits),
            )
        )
        summary["MISSING"] += 1

    # Count targets that only have rejections left as informational
    for item in items:
        key = (item["target_type"], item["target_id"])
        existing = links_by_target.get(key) or []
        if existing and all(l["link_state"] == "REJECTED" for l in existing):
            # already counted as MISSING when no other candidates; bump REJECTED info
            summary["REJECTED"] += 1

    return {
        "workspace_id": workspace_id,
        "summary": summary,
        "results": results,
        "notice": "自动对照经历库条目与本地材料，只给出候选与缺口；请选择关联或标为不符合。不能鉴定材料真伪。",
    }


def handle_evidence_get(path: str) -> tuple[int, dict[str, Any] | None, tuple[Path, str] | None]:
    """
    Route GET evidence APIs.
    Returns (status_code, json_payload, optional preview tuple).
    """
    init_db()
    parsed = urlparse(path)
    pathname = parsed.path
    qs = parse_qs(parsed.query)

    if pathname == "/api/v1/evidence/workspaces":
        return 200, {"workspaces": list_workspaces()}, None

    if pathname.startswith("/api/v1/evidence/workspaces/") and pathname.endswith("/files"):
        workspace_id = pathname[len("/api/v1/evidence/workspaces/") : -len("/files")]
        return 200, {"workspace_id": workspace_id, "files": list_files(workspace_id)}, None

    if pathname.startswith("/api/v1/evidence/workspaces/") and pathname.endswith("/evidence"):
        workspace_id = pathname[len("/api/v1/evidence/workspaces/") : -len("/evidence")]
        return 200, {"workspace_id": workspace_id, "evidence": list_workspace_evidence(workspace_id)}, None

    if pathname.startswith("/api/v1/evidence/files/") and pathname.endswith("/preview"):
        file_id = pathname[len("/api/v1/evidence/files/") : -len("/preview")]
        preview = resolve_preview_path(file_id)
        return 200, None, preview

    if pathname.startswith("/api/v1/evidence/files/"):
        file_id = pathname[len("/api/v1/evidence/files/") :]
        if "/" in file_id:
            return 404, {"error": "not found"}, None
        return 200, get_file(file_id), None

    if pathname == "/api/v1/evidence/search":
        q = (qs.get("q") or [""])[0]
        workspace_id = (qs.get("workspace_id") or [None])[0]
        return 200, search_evidence(q, workspace_id=workspace_id), None

    if pathname == "/api/v1/evidence/links":
        return 200, list_links(
            target_type=(qs.get("target_type") or [None])[0],
            target_id=(qs.get("target_id") or [None])[0],
            evidence_id=(qs.get("evidence_id") or [None])[0],
        ), None

    if pathname.startswith("/api/v1/evidence/") and not pathname.endswith("/review"):
        evidence_id = pathname[len("/api/v1/evidence/") :]
        if "/" in evidence_id or not evidence_id:
            return 404, {"error": "not found"}, None
        return 200, get_evidence(evidence_id), None

    return 404, {"error": "not found"}, None


def handle_evidence_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    init_db()
    parsed = urlparse(path)
    pathname = parsed.path

    if pathname == "/api/v1/evidence/workspaces":
        return create_workspace(str(body.get("name") or ""))

    if pathname.startswith("/api/v1/evidence/workspaces/") and pathname.endswith("/files"):
        workspace_id = pathname[len("/api/v1/evidence/workspaces/") : -len("/files")]
        return import_files(workspace_id, body.get("files") or [])

    if pathname.startswith("/api/v1/evidence/files/") and pathname.endswith("/reparse"):
        file_id = pathname[len("/api/v1/evidence/files/") : -len("/reparse")]
        if not file_id or "/" in file_id:
            raise ValueError("无效的 file_id")
        return reparse_file(file_id)

    if pathname == "/api/v1/evidence/links":
        return create_link(body)

    if pathname == "/api/v1/evidence/links/remove":
        return remove_link(body)

    if pathname == "/api/v1/evidence/check-claim":
        return check_claim_support(str(body.get("claim_text") or ""), str(body.get("evidence_id") or ""))

    if pathname.startswith("/api/v1/evidence/workspaces/") and pathname.endswith("/match-resume"):
        workspace_id = pathname[len("/api/v1/evidence/workspaces/") : -len("/match-resume")]
        return match_resume(workspace_id, body)

    if pathname.startswith("/api/v1/evidence/") and pathname.endswith("/review"):
        evidence_id = pathname[len("/api/v1/evidence/") : -len("/review")]
        return review_evidence(evidence_id, body)

    raise ValueError("Route not found")


def handle_evidence_delete(path: str) -> dict[str, Any]:
    init_db()
    parsed = urlparse(path)
    pathname = parsed.path
    if pathname.startswith("/api/v1/evidence/workspaces/"):
        workspace_id = pathname[len("/api/v1/evidence/workspaces/") :]
        if "/" in workspace_id or not workspace_id:
            raise ValueError("Route not found")
        return delete_workspace(workspace_id)
    raise ValueError("Route not found")
