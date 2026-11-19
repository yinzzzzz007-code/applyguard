from __future__ import annotations

import json
from dataclasses import dataclass
from time import monotonic
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SourceError(ValueError):
    pass


@dataclass
class Snapshot:
    jobs: list[dict]
    complete: bool
    skipped: int = 0
    notice: str | None = None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class JobSourceAdapter:
    source_id: str
    source_name: str
    company: str
    source_url: str
    hosts: frozenset[str]
    max_body = 3_000_000
    api_headers: dict[str, str] = {}

    def __init__(self):
        self.deadline = monotonic() + 165
        self.opener = build_opener(NoRedirect())

    def request(self, url: str, body: dict | None = None, *, form: bool = False) -> str:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in self.hosts or parsed.username or parsed.port not in (None, 443):
            raise SourceError("招聘来源地址不在允许范围")
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise SourceError("来源刷新超时")
        headers = {"Accept": "application/json,text/html", "User-Agent": "ApplyGuard-JobRadar/1.0"}
        headers.update(self.api_headers)
        if body is not None:
            from urllib.parse import urlencode
            data = urlencode(body).encode() if form else json.dumps(body).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded;charset=utf-8" if form else "application/json"
            headers["Origin"] = f"https://{urlsplit(self.source_url).hostname}"
        else:
            data = None
        req = Request(url, data, headers)
        try:
            with self.opener.open(req, timeout=min(12, remaining)) as response:
                chunks, size = [], 0
                while True:
                    if monotonic() > self.deadline:
                        raise SourceError("来源刷新超时")
                    chunk = response.read1(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_body:
                        raise SourceError("来源响应超过体积上限")
                    chunks.append(chunk)
        except HTTPError as exc:
            raise SourceError(f"官网返回 HTTP {exc.code}") from exc
        except OSError as exc:
            raise SourceError("官网连接失败或超时") from exc
        return b"".join(chunks).decode("utf-8")

    def parse(self, text: str) -> tuple[list[dict], int]:
        raise NotImplementedError

    def normalize(self, row: dict) -> dict:
        raise NotImplementedError

    def fetch(self) -> Snapshot:
        raise NotImplementedError

    def health_check(self) -> dict:
        rows, total = self.parse(self.request(self.source_url))
        return {"visible": len(rows), "reported": total}

    def job(self, external_id, title, location, kind, url, responsibilities, requirements, **fields):
        if not external_id or not title or not url or not (responsibilities or requirements):
            raise SourceError("岗位缺少编号、名称、官方链接或职责要求")
        official_url = urljoin(self.source_url, url)
        link = urlsplit(official_url)
        if link.scheme != "https" or link.hostname not in self.hosts or link.username or link.port not in (None, 443):
            raise SourceError("岗位链接不是该公司的官方地址")
        return {
            "external_id": str(external_id), "title": title, "company": self.company,
            "location": location or "", "recruitment_type": kind, "url": official_url,
            "responsibilities": responsibilities or "", "requirements": requirements or "",
            "source_url": self.source_url, "status": "open", **fields,
        }

    def snapshot(self, rows: list[dict], complete: bool) -> Snapshot:
        jobs, skipped = {}, 0
        for row in rows:
            try:
                job = self.normalize(row)
                if job["external_id"] in jobs:
                    complete = False
                    skipped += 1
                jobs[job["external_id"]] = job
            except (ValueError, TypeError, KeyError, AttributeError):
                skipped += 1
        if rows and not jobs:
            raise SourceError("官网岗位字段已变化，无法识别详情")
        return Snapshot(list(jobs.values()), complete and not skipped, skipped)
