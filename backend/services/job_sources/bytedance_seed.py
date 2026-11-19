from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .base import JobSourceAdapter, SourceError


class BytedanceSeed(JobSourceAdapter):
    source_id = "bytedance_seed"
    source_name = "字节跳动 Seed 招聘"
    company = "字节跳动 Seed"
    source_url = "https://seed.bytedance.com/zh/career"
    hosts = frozenset({"seed.bytedance.com", "jobs.bytedance.com"})

    def parse(self, text):
        jobs = {}
        for match in re.finditer(r'"SubJobZh"\s*:\s*(\{[^{}]*\})', text):
            row = json.loads(match[1])
            path = urlsplit(row.get("ExternalLink", "")).path
            post_id = re.search(r"/position/(?:detail/)?(\d{12,25})(?:/detail)?/?$", path)
            if post_id and row.get("JobName"):
                jobs.setdefault(post_id[1], {**row, "id": post_id[1]})
        if not jobs:
            raise SourceError("Seed 页面未找到公开热招岗位")
        return list(jobs.values()), len(jobs)

    def normalize(self, row):
        kind = row.get("JobTypeName") or "招聘类型未公布"
        campus = kind in {"校招", "实习"}
        section = "campus" if campus else "experienced"
        external_id = row["id"]
        return self.job(external_id, row.get("title") or row["JobName"], row.get("City"), kind,
                        f"https://jobs.bytedance.com/{section}/position/{external_id}/detail",
                        row.get("description"), row.get("requirement"),
                        published_at=row.get("published_at"), status=row.get("status", "open"),
                        details_available=row.get("details_available", True))

    def fetch(self):
        rows, _ = self.parse(self.request(self.source_url))
        skipped = 0
        for row in rows:
            try:
                portal_type = 1 if row["JobTypeName"] in {"校招", "实习"} else 2
                api = f"https://jobs.bytedance.com/api/v1/job/posts/{row['id']}?portal_type={portal_type}"
                data = json.loads(self.request(api))
                detail = data["data"]["job_post_detail"]
                if data["code"] != 0 or detail["id"] != row["id"] or not (detail.get("description") or detail.get("requirement")):
                    raise SourceError("Seed 公开详情未返回匹配记录")
                row.update(detail)
                row["status"] = {0: "closed", 1: "open"}.get(detail.get("channel_online_status"), "unknown")
                if type(detail.get("publish_time")) is int:
                    row["published_at"] = datetime.fromtimestamp(detail["publish_time"] / 1000, timezone.utc).isoformat()
            except (ValueError, KeyError, TypeError, OSError, OverflowError):
                skipped += 1
                previous = getattr(self, "previous", {}).get(row["id"], {})
                if previous.get("details_available"):
                    row.update(title=previous["title"], City=previous["location"],
                               description=previous.get("responsibilities"), requirement=previous["requirements"],
                               status=previous["status"], published_at=previous["published_at"])
                else:
                    row.update(description="此岗位来自 Seed 官网热招目录。请打开官方详情查看完整职责和要求。",
                               status="unknown", details_available=False)
        snapshot = self.snapshot(rows, False)
        snapshot.skipped += skipped
        return snapshot
