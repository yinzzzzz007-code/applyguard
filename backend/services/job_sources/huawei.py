from __future__ import annotations

import json
from urllib.parse import urlencode

from .base import JobSourceAdapter, SourceError

APP_ID = "app_000000035886"


class Huawei(JobSourceAdapter):
    source_id = "huawei"
    source_name = "华为校园招聘"
    company = "华为"
    source_url = "https://career.huawei.com/cn/campus-recruitment-job-list"
    hosts = frozenset({"career.huawei.com", "apigw-dgg-b0.huawei.com"})
    api_headers = {"X-HW-ID": APP_ID, "X-Jalor-TenantAlias": "hcm", "X-Language": "zh_CN",
                   "Referer": "https://career.huawei.com/", "X-Referer": "https://career.huawei.com/cn",
                   "X-ALB-Gray": "prod", "Accept-Language": "zh-CN"}

    def api(self, action, data):
        url = f"https://apigw-dgg-b0.huawei.com/api/apig/channelhw/recruitmentPosition/pub/{action}?X-HW-ID={APP_ID}"
        response = json.loads(self.request(url, data))
        if response.get("status") != "SUCCESS":
            raise SourceError("华为官网未返回公开岗位数据")
        return response.get("data")

    def parse(self, text):
        payload = json.loads(text)
        pagination = payload.get("pageVO") if isinstance(payload, dict) else None
        if not isinstance(pagination, dict):
            raise SourceError("华为官网响应缺少目录分页信息")
        rows, total = payload.get("result"), pagination.get("totalRows")
        if not isinstance(rows, list) or type(total) is not int or total < len(rows):
            raise SourceError("华为岗位总数与目录不一致")
        return rows, total

    def normalize(self, row):
        key = row["advertisementId"]
        kind = "实习" if str(row.get("jobType")) == "1" else "校招"
        return self.job(key, row["jobName"], (row.get("workPlace") or "")[:200], kind,
                        "/cn/job-details?" + urlencode({"advertisementId": key}),
                        row.get("mainBusiness"), row.get("jobRequire"), education=row.get("degree"),
                        experience=row.get("workYear"), published_at=row.get("releaseDate"),
                        source_updated_at=str(row.get("lastUpdateDate") or ""), details_available=row.get("details_available", True))

    def health_check(self):
        data = self.api("getJobPage", {"curPage": 1, "pageSize": 10, "jobType": "CR"})
        rows, total = self.parse(json.dumps(data))
        return {"visible": len(rows), "reported": total}

    def fetch(self):
        rows, total, complete = [], None, True
        for page in range(1, 41):
            data = self.api("getJobPage", {"curPage": page, "pageSize": 10, "jobType": "CR"})
            page_rows, reported = self.parse(json.dumps(data))
            complete &= (data["pageVO"].get("curPage") == page and total in (None, reported))
            total = reported
            rows.extend(page_rows)
            if len(rows) >= total or not page_rows:
                break
        detailed, skipped = 0, 0
        previous_jobs = getattr(self, "previous", {})
        rows.sort(key=lambda row: bool(previous_jobs.get(str(row.get("advertisementId")), {}).get("details_available")))
        for row in rows:
            plain = (row.get("mainBusiness") or "") + (row.get("jobRequire") or "")
            if len(plain.strip()) >= 20 and "请您详见岗位意向" not in plain:
                continue
            previous = previous_jobs.get(str(row.get("advertisementId")), {})
            if previous.get("details_available") and previous.get("source_updated_at") and previous["source_updated_at"] == str(row.get("lastUpdateDate") or ""):
                row.update(mainBusiness=previous.get("responsibilities"), jobRequire=previous.get("requirements"))
                continue
            if detailed < 16 and row.get("jobId"):
                detailed += 1
                try:
                    intentions = self.api("getPositionIntentionList", {"jobId": row["jobId"]})
                    description, requirements = self.intention_text(intentions)
                    if description or requirements:
                        row.update(mainBusiness=description, jobRequire=requirements)
                        continue
                except (ValueError, TypeError, KeyError):
                    skipped += 1
            if previous.get("details_available"):
                row.update(mainBusiness=previous.get("responsibilities"), jobRequire=previous.get("requirements"),
                           lastUpdateDate=previous.get("source_updated_at"))
            else:
                row.update(mainBusiness="此岗位已在华为官网列出。详细职责和任职要求请打开官网并查看相应岗位意向。",
                           jobRequire="", details_available=False)
        snapshot = self.snapshot(rows, complete and len(rows) == total)
        snapshot.skipped += skipped
        return snapshot

    @staticmethod
    def intention_text(data):
        if not isinstance(data, list):
            return "", ""
        def field(names, limit):
            from backend.services.job_radar import _description
            texts = []
            for row in data:
                if not isinstance(row, dict):
                    continue
                value = next((row[key] for key in names if isinstance(row.get(key), str) and row[key].strip()), "")
                if value:
                    texts.append(_description(value[:16000], "岗位意向"))
            text = "\n".join(dict.fromkeys(texts))
            suffix = "\n其余岗位意向请查看官网。"
            return text[:limit - len(suffix)] + suffix if len(text) > limit else text
        return field(("jobResponsibilities", "mainBusiness", "jobDuty"), 6000), field(
            ("jobDemand", "jobRequire", "jobRequirement"), 10000)
