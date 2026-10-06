from __future__ import annotations

import json
import logging
import mimetypes
import os
import sys
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from backend.services.career_vault import CareerVault
from backend.services.draft_store import DraftStore
from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.resume_selector import ResumeSelector
from backend.services.skill_router import SkillRouter, WorkflowStopped, validate_request_ids
from backend.services.model_client import HttpModelClient
from backend.services.pdf_extract import MAX_PDF_BYTES, extract_resume_pdf

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FRONTEND_DIR = ROOT / "frontend"
CAREER_VAULT_PATH = DATA_DIR / "career-vault.seed.json"


def _draft_store() -> DraftStore:
    return DraftStore(Path(os.getenv("APPLYGUARD_LOCAL_DATA_DIR", str(DATA_DIR / "local"))), CAREER_VAULT_PATH)


def _active_vault_path(candidate_id: str) -> Path:
    saved = _draft_store().load(candidate_id)
    return _draft_store()._path(candidate_id) if saved else CAREER_VAULT_PATH


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE from repo-root .env into os.environ (does not override existing vars)."""
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or not value:
            continue
        # Allow .env to fill blanks; do not clobber a non-empty shell export.
        if os.environ.get(key):
            continue
        os.environ[key] = value


_load_dotenv(ROOT / ".env")


def _load_json(name: str) -> dict[str, Any]:
    with (DATA_DIR / name).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _error(code: str, message: str, trace_id: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "trace_id": trace_id,
        }
    }


def build_mock_workflow(request: dict[str, Any]) -> dict[str, Any]:
    """Build one deterministic end-to-end proposal response."""
    trace_id = request.get("trace_id") or f"trace_{uuid.uuid4().hex[:12]}"
    candidate_id = request.get("candidate_id")
    jd_text = request.get("jd_text")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError("candidate_id must be a non-empty string")
    if not isinstance(jd_text, str) or len(jd_text.strip()) < 20:
        raise ValueError("jd_text must contain at least 20 characters")

    if len(jd_text) > 20000:
        raise ValueError("jd_text must contain at most 20000 characters")
    validate_request_ids(request)
    if request.get("parse_mode") not in (None, "fixture", "dynamic", "offline"):
        raise ValueError("parse_mode must be fixture, dynamic or offline")
    if request.get("parse_mode") in ("dynamic", "offline") or (request.get("parse_mode") is None and os.getenv("APPLYGUARD_AI_API_KEY")):
        model = HttpModelClient() if request.get("parse_mode") != "offline" and os.getenv("APPLYGUARD_AI_API_KEY") else None
        return SkillRouter(_active_vault_path(candidate_id), _load_json("form-mapping.example.json"), model=model).run({**request, "trace_id": trace_id})

    application_id = request.get("application_id") or "app_demo_001"
    # JD Parser belongs to C. B deliberately uses this frozen parsed-JD fixture.
    parsed_jd = _load_json("parsed-jd.example.json")
    career_vault = CareerVault.from_json(_active_vault_path(candidate_id))
    experiences = career_vault.list_experiences(candidate_id)
    evidence_match = EvidenceMatcher().match(parsed_jd, experiences)
    selection = ResumeSelector().select(evidence_match, experiences, application_id, max_claims=1)
    resume_claims = selection.claims
    verification_results = _load_json("claim-verification.example.json")["results"]
    form_mapping = _load_json("form-mapping.example.json")
    risk_result = _load_json("risk-result.example.json")

    form_mapping["application_id"] = application_id
    risk_result["application_id"] = application_id

    step_trace = [
        {"step": "Career Vault", "status": "COMPLETED"},
        {"step": "JD Parser", "status": "COMPLETED"},
        {"step": "Evidence Matcher", "status": "COMPLETED"},
        {"step": "Resume Selector", "status": "COMPLETED"},
        {"step": "Claim Validator", "status": "COMPLETED"},
        {"step": "ATS Form Mapper", "status": "COMPLETED"},
        {"step": "Risk Check", "status": "COMPLETED"},
        {"step": "Human Confirmation", "status": "PENDING"},
        {"step": "Audit Record", "status": "CREATED"},
    ]

    return {
        "trace_id": trace_id,
        "application_id": application_id,
        "candidate_id": candidate_id,
        "execution_mode": "DETERMINISTIC_FIXTURE",
        "mock_notice": "经历、证据匹配和简历选择使用确定性规则；此固定样例不会重新解析本次输入的岗位说明。",
        "workflow_status": "AWAITING_HUMAN_CONFIRMATION",
        "parsed_jd": parsed_jd,
        "evidence_match": evidence_match,
        "resume_claims": resume_claims,
        "resume_selection": {
            "mode": "DETERMINISTIC_EVIDENCE_CONSTRAINED",
            "removed_claims": selection.removed_claims,
            "max_claims": 1,
            "max_characters": 420,
        },
        "claim_verification": verification_results,
        "ats_form_mapping": form_mapping,
        "risk_result": risk_result,
        "human_confirmation": {
            "required": True,
            "reason": "The user must confirm the resume claims and the unmapped ATS field before submission.",
            "allowed_actions": ["CONFIRM", "EDIT", "CANCEL"],
        },
        "audit_record": {
            "audit_id": f"audit_{uuid.uuid4().hex[:12]}",
            "application_id": application_id,
            "version": 1,
            "created_at": _utc_now(),
            "event": "APPLICATION_DRAFT_PREPARED",
            "actor": "applyguard.mock-workflow",
            "trace_id": trace_id,
            "decision": "PENDING",
        },
        "step_trace": step_trace,
    }


class ApplyGuardHandler(BaseHTTPRequestHandler):
    server_version = "ApplyGuard/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        logging.info("request client=%s message=%s", self.client_address[0], format % args)

    def _cors_headers(self) -> None:
        # Proposal local UI (Vite :5173) may call the API directly when not using the proxy.
        origin = self.headers.get("Origin", "")
        if origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Vary", "Origin")

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        parsed = urlsplit(self.path)
        path = parsed.path
        if path in ("/api/v1/vault", "/api/v1/vault/draft"):
            candidate_id = parse_qs(parsed.query).get("candidate_id", ["cand_demo_001"])[0]
            try:
                saved = _draft_store().load(candidate_id)
                if path.endswith("/draft"):
                    if not saved:
                        self._send_json(HTTPStatus.NOT_FOUND, _error("DRAFT_NOT_FOUND", "没有已保存草稿", trace_id))
                    else:
                        self._send_json(HTTPStatus.OK, {"form": saved["form"], "version": saved["version"], "saved_at": saved["saved_at"]})
                else:
                    if saved:
                        self._send_json(HTTPStatus.OK, saved["vault"])
                    else:
                        self._send_json(HTTPStatus.OK, _load_json("career-vault.seed.json"))
            except ValueError as exc:
                self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, _error("VALIDATION_ERROR", str(exc), trace_id))
            except (OSError, json.JSONDecodeError):
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, _error("DRAFT_READ_FAILED", "无法读取本地草稿", trace_id))
            return
        if path.startswith(("/assets/", "/data/", "/prerecorded/")):
            relative = unquote(path).lstrip("/")
            base = FRONTEND_DIR / "dist" if (FRONTEND_DIR / "dist" / "index.html").exists() else FRONTEND_DIR / "public"
            asset = (base / relative).resolve()
            if asset.is_file() and asset.is_relative_to(base.resolve()):
                self._send_file(asset)
            else:
                self._send_json(HTTPStatus.NOT_FOUND, _error("NOT_FOUND", "Route not found", trace_id))
            return
        if path == "/":
            # Prefer Vite production build when present; otherwise legacy static demo.
            dist_index = FRONTEND_DIR / "dist" / "index.html"
            legacy = FRONTEND_DIR / "legacy-demo.html"
            if dist_index.exists():
                self._send_html(dist_index)
            elif legacy.exists():
                self._send_html(legacy)
            else:
                self._send_html(FRONTEND_DIR / "index.html")
            return
        if path == "/legacy-demo.html":
            self._send_html(FRONTEND_DIR / "legacy-demo.html")
            return
        if path.startswith("/assets/") and (FRONTEND_DIR / "dist" / path.lstrip("/")).exists():
            asset = FRONTEND_DIR / "dist" / path.lstrip("/")
            data = asset.read_bytes()
            ctype = "application/javascript" if asset.suffix == ".js" else "text/css" if asset.suffix == ".css" else "application/octet-stream"
            self.send_response(HTTPStatus.OK.value)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "applyguard-foundation",
                    "version": "0.1.0",
                    "time": _utc_now(),
                },
            )
            return
        if path in ("/jd", "/match", "/resume", "/claims", "/ats", "/confirm", "/history") and (FRONTEND_DIR / "dist" / "index.html").exists():
            self._send_html(FRONTEND_DIR / "dist" / "index.html")
            return
        self._send_json(HTTPStatus.NOT_FOUND, _error("NOT_FOUND", "Route not found", trace_id))

    def do_POST(self) -> None:  # noqa: N802
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        if self.path == "/api/v1/vault/pdf-extract":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_PDF_BYTES:
                    self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, _error("PDF_SIZE_INVALID", "PDF 文件大小须在 1 字节至 8 MB 之间", trace_id))
                    return
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/pdf":
                    raise ValueError("请上传 PDF 文件")
                response = extract_resume_pdf(self.rfile.read(length))
            except ValueError as exc:
                self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, _error("PDF_INVALID", str(exc), trace_id))
                return
            self._send_json(HTTPStatus.OK, response)
            return
        if self.path not in ("/api/v1/workflow/mock", "/api/v1/vault/draft"):
            self._send_json(HTTPStatus.NOT_FOUND, _error("NOT_FOUND", "Route not found", trace_id))
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= 262144:
                raise ValueError("request body must be between 1 and 262144 bytes")
            raw = self.rfile.read(content_length)
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("request body must be a JSON object")
            if self.path == "/api/v1/vault/draft":
                if not isinstance(request.get("form"), dict):
                    raise ValueError("form must be an object")
                saved = _draft_store().save(request.get("candidate_id", ""), request["form"])
                response = {"form": saved["form"], "version": saved["version"], "saved_at": saved["saved_at"]}
            else:
                response = build_mock_workflow(request)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, _error("INVALID_JSON", "Request body is not valid JSON", trace_id))
            return
        except ValueError as exc:
            details = [{"step_trace": exc.step_trace, "audit_record": exc.audit_record}] if isinstance(exc, WorkflowStopped) else None
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR if isinstance(exc, WorkflowStopped) and exc.code == "INTERNAL_ERROR" else HTTPStatus.UNPROCESSABLE_ENTITY,
                _error(exc.code if isinstance(exc, WorkflowStopped) else "VALIDATION_ERROR", str(exc), exc.trace_id if isinstance(exc, WorkflowStopped) else trace_id, details),
            )
            return
        except OSError:
            logging.exception("Draft write failed, trace_id=%s", trace_id)
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, _error("DRAFT_WRITE_FAILED", "草稿写入失败，旧版本未更改", trace_id))
            return
        except Exception:
            logging.exception("Unexpected workflow error, trace_id=%s", trace_id)
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, _error("INTERNAL_ERROR", "Workflow failed", trace_id))
            return

        self._send_json(HTTPStatus.OK, response)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ApplyGuardHandler)


def main() -> None:
    host = os.getenv("APPLYGUARD_HOST", "127.0.0.1")
    port = int(os.getenv("APPLYGUARD_PORT", "8000"))
    level = os.getenv("APPLYGUARD_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    server = create_server(host, port)
    logging.info("ApplyGuard foundation listening at http://%s:%s", host, port)
    logging.info(
        "AI config: key=%s base=%s model=%s",
        "set" if os.getenv("APPLYGUARD_AI_API_KEY") else "missing",
        os.getenv("APPLYGUARD_AI_BASE_URL", ""),
        os.getenv("APPLYGUARD_AI_MODEL", ""),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutdown requested")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
