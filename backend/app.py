from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from backend.services.career_vault import CareerVault
from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.sag_auxiliary import augment_match_with_sag
from backend.services.evidence_workspace import (
    handle_evidence_delete,
    handle_evidence_get,
    handle_evidence_post,
)
from backend.services.local_store import load_resume_draft, save_resume_draft
from backend.services.resume_draft_vault import experiences_from_resume_draft
from backend.services.resume_parser import parse_resume_pdf
from backend.services.resume_selector import ResumeSelector
from backend.services.skill_router import SkillRouter, WorkflowStopped, validate_request_ids
from backend.services.model_client import HttpModelClient
from backend.services import job_radar

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FRONTEND_DIR = ROOT / "frontend"
CAREER_VAULT_PATH = DATA_DIR / "career-vault.seed.json"


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
    target_job = job_radar.validate_target(request)
    if target_job and request.get("parse_mode") not in ("offline", "dynamic"):
        raise ValueError("关联岗位必须使用 offline 或 dynamic 解析，不允许演示 fixture 替代原文")
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
        response = SkillRouter(CAREER_VAULT_PATH, _load_json("form-mapping.example.json"), model=model).run({**request, "trace_id": trace_id})
        if target_job:
            response["target_job"] = target_job
            # These labels are exact metadata already included in the checked source text.
            response["parsed_jd"]["title"] = target_job["title"]
            response["parsed_jd"]["company"] = target_job["company"]
        return response

    application_id = request.get("application_id") or "app_demo_001"
    # JD Parser belongs to C. B deliberately uses this frozen parsed-JD fixture.
    parsed_jd = _load_json("parsed-jd.example.json")
    draft = request.get("resume_draft")
    if not isinstance(draft, dict):
        draft = load_resume_draft()
    vault_mode = "DETERMINISTIC_SEED"
    if isinstance(draft, dict):
        experiences = experiences_from_resume_draft(draft)
        if experiences:
            vault_mode = "LOCAL_RESUME_DRAFT"
            candidate_id = experiences[0]["candidate_id"]
    if vault_mode == "DETERMINISTIC_SEED":
        career_vault = CareerVault.from_json(CAREER_VAULT_PATH)
        experiences = career_vault.list_experiences(candidate_id)
    evidence_match = EvidenceMatcher().match(parsed_jd, experiences)
    evidence_match = augment_match_with_sag(parsed_jd, experiences, evidence_match)
    selection = ResumeSelector().select(evidence_match, experiences, application_id, max_claims=1)
    resume_claims = selection.claims
    verification_results = _load_json("claim-verification.example.json")["results"]
    # When using the user's draft, verification fixture IDs won't match — synthesize NEEDS_REVIEW.
    if vault_mode == "LOCAL_RESUME_DRAFT":
        verification_results = [
            {
                "claim_id": claim["claim_id"],
                "state": "NEEDS_REVIEW",
                "unsupported_fragments": [],
                "explanation": "来自本机经历库草稿；请在陈述核验页人工确认。",
                "support_score": float(claim.get("evidence_support_score") or 0),
                "grounded": bool(claim.get("evidence_ids")),
            }
            for claim in resume_claims
        ]
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

    notice = (
        "已使用本机经历库草稿作为陈述来源（非演示种子）。"
        if vault_mode == "LOCAL_RESUME_DRAFT"
        else "Career Vault, Evidence Matcher, and Resume Selector use deterministic B baseline logic. JD Parser remains a fixed parsed-jd.example.json fixture; the submitted JD is not dynamically parsed."
    )

    if "sag_auxiliary" in evidence_match:
        notice += f" SAG auxiliary mode: {evidence_match['sag_auxiliary']['mode']}; retrieval does not verify claims."

    return {
        "trace_id": trace_id,
        "application_id": application_id,
        "candidate_id": candidate_id,
        "execution_mode": "DETERMINISTIC_FIXTURE",
        "mock_notice": notice,
        "workflow_status": "AWAITING_HUMAN_CONFIRMATION",
        "parsed_jd": parsed_jd,
        "evidence_match": evidence_match,
        "resume_claims": resume_claims,
        "resume_selection": {
            "mode": "DETERMINISTIC_EVIDENCE_CONSTRAINED",
            "removed_claims": [
                {**row, "text": next(
                    (c["text"] for exp in experiences for c in exp.get("claims", []) if c["claim_id"] == row["claim_id"]),
                    row.get("text") or "",
                )}
                for row in selection.removed_claims
            ],
            "max_claims": 1,
            "max_characters": 420,
        },
        "claim_verification": verification_results,
        "ats_form_mapping": form_mapping,
        "risk_result": risk_result,
        "component_modes": {"career_vault": vault_mode},
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
        try:
            parsed_origin = urlsplit(origin)
        except ValueError:
            return
        if (parsed_origin.scheme == "http" and parsed_origin.hostname in {"127.0.0.1", "localhost"}
                and not parsed_origin.username and not parsed_origin.password and not parsed_origin.path
                and not parsed_origin.query and not parsed_origin.fragment):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Vary", "Origin")

    def _send_bytes(self, status: HTTPStatus, data: bytes, content_type: str) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self._cors_headers()
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

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

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self._cors_headers()
        self.end_headers()

    def _send_spa_index(self) -> None:
        """Serve the React shell so client routes like /jd keep working on refresh."""
        dist_index = FRONTEND_DIR / "dist" / "index.html"
        legacy = FRONTEND_DIR / "legacy-demo.html"
        if dist_index.exists():
            self._send_html(dist_index)
        elif legacy.exists():
            self._send_html(legacy)
        else:
            self._send_html(FRONTEND_DIR / "index.html")

    def _send_static_file(self, path: Path) -> bool:
        if not path.is_file():
            return False
        data = path.read_bytes()
        suffix = path.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
        }.get(suffix, "application/octet-stream")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        return True

    def do_GET(self) -> None:  # noqa: N802
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        # Strip query string for static / SPA routing
        path_only = self.path.split("?", 1)[0] or "/"

        if path_only == "/":
            self._send_spa_index()
            return
        if path_only == "/legacy-demo.html":
            self._send_html(FRONTEND_DIR / "legacy-demo.html")
            return

        # Vite build assets + public/ files (e.g. /data/career-vault.seed.json)
        if path_only.startswith("/assets/") or path_only.startswith("/data/") or path_only.startswith("/prerecorded/") or path_only in {
            "/favicon.svg",
            "/favicon.ico",
        }:
            rel = path_only.lstrip("/")
            for root in (FRONTEND_DIR / "dist", FRONTEND_DIR / "public", FRONTEND_DIR):
                decoded = unquote(rel)
                candidate = (root / decoded).resolve()
                if ".." in Path(decoded).parts or not candidate.is_relative_to(root.resolve()):
                    continue
                if self._send_static_file(candidate):
                    return

        if path_only == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "applyguard-foundation",
                    "version": "1.0.0",
                    "time": _utc_now(),
                },
            )
            return
        if path_only == "/api/v1/jobs" or path_only.startswith("/api/v1/jobs/"):
            try:
                payload = job_radar.handle_get(self.path)
            except job_radar.RadarUnavailable as exc:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, _error("RADAR_UNAVAILABLE", str(exc), trace_id))
                return
            except ValueError as exc:
                missing = str(exc) == "Route not found"
                self._send_json(HTTPStatus.NOT_FOUND if missing else HTTPStatus.UNPROCESSABLE_ENTITY,
                                _error("NOT_FOUND" if missing else "VALIDATION_ERROR", str(exc), trace_id))
                return
            except Exception:
                logging.exception("Job library GET failed, trace_id=%s", trace_id)
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, _error("INTERNAL_ERROR", "Job library request failed", trace_id))
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if path_only == "/api/v1/resume/draft":
            try:
                form = load_resume_draft()
            except ValueError as exc:
                self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, _error("VALIDATION_ERROR", str(exc), trace_id))
                return
            if form is None:
                self._send_json(HTTPStatus.OK, {"exists": False, "form": None})
                return
            self._send_json(HTTPStatus.OK, {"exists": True, "form": form})
            return
        if path_only.startswith("/api/v1/evidence"):
            try:
                status, payload, preview = handle_evidence_get(self.path)
            except ValueError as exc:
                self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, _error("VALIDATION_ERROR", str(exc), trace_id))
                return
            except Exception:
                logging.exception("Evidence GET failed, trace_id=%s", trace_id)
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, _error("INTERNAL_ERROR", "Evidence request failed", trace_id))
                return
            if preview is not None:
                path, media = preview
                self._send_bytes(HTTPStatus.OK, path.read_bytes(), media)
                return
            if status == 404:
                self._send_json(HTTPStatus.NOT_FOUND, _error("NOT_FOUND", "Route not found", trace_id))
                return
            assert payload is not None
            self._send_json(HTTPStatus.OK, payload)
            return

        # Serve only known client routes; unknown paths retain the JSON 404 API contract.
        spa_routes = {"/vault", "/evidence", "/jobs", "/jd", "/match", "/resume", "/claims", "/ats", "/confirm", "/history"}
        if path_only in spa_routes:
            self._send_spa_index()
            return
        self._send_json(HTTPStatus.NOT_FOUND, _error("NOT_FOUND", "Route not found", trace_id))

    def do_DELETE(self) -> None:  # noqa: N802
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        if not self.path.startswith("/api/v1/evidence"):
            self._send_json(HTTPStatus.NOT_FOUND, _error("NOT_FOUND", "Route not found", trace_id))
            return
        try:
            response = handle_evidence_delete(self.path)
        except ValueError as exc:
            code = "NOT_FOUND" if str(exc) == "Route not found" else "VALIDATION_ERROR"
            status = HTTPStatus.NOT_FOUND if code == "NOT_FOUND" else HTTPStatus.UNPROCESSABLE_ENTITY
            self._send_json(status, _error(code, str(exc), trace_id))
            return
        except Exception:
            logging.exception("Evidence DELETE failed, trace_id=%s", trace_id)
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, _error("INTERNAL_ERROR", "Evidence delete failed", trace_id))
            return
        self._send_json(HTTPStatus.OK, response)

    def do_POST(self) -> None:  # noqa: N802
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        if self.path == "/api/v1/resume/parse":
            max_bytes = 8_000_000
        elif self.path == "/api/v1/resume/draft":
            max_bytes = 400_000
        elif self.path in {"/api/v1/workflow/mock", "/api/v1/workflow/reverify"}:
            max_bytes = 262144
        elif self.path.startswith("/api/v1/evidence"):
            max_bytes = 12_000_000  # single-file import batches; keep under proxy limits
        elif self.path == "/api/v1/jobs" or self.path.startswith("/api/v1/jobs/"):
            max_bytes = 2_000_000
        else:
            self._send_json(HTTPStatus.NOT_FOUND, _error("NOT_FOUND", "Route not found", trace_id))
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= max_bytes:
                raise ValueError(
                    f"request body must be between 1 and {max_bytes} bytes "
                    f"(got {content_length}). 请一次少选几个文件，或确认后端已重启。"
                )
            raw = self.rfile.read(content_length)
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("request body must be a JSON object")
            if self.path == "/api/v1/resume/parse":
                response = parse_resume_pdf(request.get("pdf_base64", ""), request.get("filename", "resume.pdf"), parse_mode=request.get("parse_mode", "offline"))
            elif self.path == "/api/v1/resume/draft":
                response = save_resume_draft(request)
            elif self.path.startswith("/api/v1/evidence"):
                response = handle_evidence_post(self.path, request)
            elif self.path == "/api/v1/jobs" or self.path.startswith("/api/v1/jobs/"):
                response = job_radar.handle_post(self.path, request)
            elif self.path == "/api/v1/workflow/reverify":
                from backend.services.reverification import reverify_workflow
                response = reverify_workflow(CAREER_VAULT_PATH, request)
            else:
                response = build_mock_workflow(request)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as exc:
            logging.warning("Client disconnected during POST %s: %s", self.path, exc)
            return
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, _error("INVALID_JSON", "Request body is not valid JSON", trace_id))
            return
        except job_radar.RadarUnavailable as exc:
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, _error("RADAR_UNAVAILABLE", str(exc), trace_id))
            return
        except ValueError as exc:
            if str(exc) == "Route not found":
                self._send_json(HTTPStatus.NOT_FOUND, _error("NOT_FOUND", "Route not found", trace_id))
                return
            details = [{"step_trace": exc.step_trace, "audit_record": exc.audit_record}] if isinstance(exc, WorkflowStopped) else None
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR if isinstance(exc, WorkflowStopped) and exc.code == "INTERNAL_ERROR" else HTTPStatus.UNPROCESSABLE_ENTITY,
                _error(exc.code if isinstance(exc, WorkflowStopped) else "VALIDATION_ERROR", str(exc), exc.trace_id if isinstance(exc, WorkflowStopped) else trace_id, details),
            )
            return
        except Exception:
            logging.exception("Unexpected workflow error, trace_id=%s path=%s", trace_id, self.path)
            try:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, _error("INTERNAL_ERROR", "Workflow failed", trace_id))
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                return
            return

        try:
            self._send_json(HTTPStatus.OK, response)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            logging.warning("Client disconnected before response for %s", self.path)


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
