from __future__ import annotations

import json
import re
from urllib.parse import quote

from .base import JobSourceAdapter, SourceError


class Baidu(JobSourceAdapter):
    source_id = "baidu"
    source_name = "百度校园招聘"
    company = "百度"
    source_url = "https://talent.baidu.com/jobs/list?recruitType=INTERN"
    hosts = frozenset({"talent.baidu.com"})

    def parse(self, text):
        match = re.search(r"window\.__INITIAL_DATA__\s*=\s*(.*?)</script>", text, re.S)
        if not match:
            raise SourceError("百度页面缺少公开岗位目录")
        raw = re.sub(r'"(?:[^"\\]|\\.)*"|\bundefined\b',
                     lambda part: "null" if part[0] == "undefined" else part[0], match[1])
        try:
            data = json.JSONDecoder().raw_decode(raw)[0]["listData"]
            jobs, total = data["listDetailData"], data["total"]
        except (KeyError, ValueError, TypeError) as exc:
            raise SourceError("百度岗位结构变化") from exc
        if not isinstance(jobs, list) or type(total) is not int or total < len(jobs):
            raise SourceError("百度岗位总数与目录不一致")
        return jobs, total

    def normalize(self, row):
        external_id = row["postId"]
        return self.job(external_id, row["name"], row.get("workPlace"), row.get("projectType") or "实习",
                        "/jobs/detail/INTERN/" + quote(external_id, safe=""),
                        row.get("workContent"), row.get("serviceCondition"),
                        education=row.get("education"), experience=row.get("workYears"), published_at=row.get("publishDate"))

    def fetch(self):
        rows, total = self.parse(self.request(self.source_url))
        if len(rows) == total:
            return self.snapshot(rows, True)
        try:
            pages, expected = [], None
            for page in range(1, 41):
                response = json.loads(self.request("https://talent.baidu.com/httservice/getPostListNew", {
                    "recruitType": "INTERN", "curPage": page, "pageSize": 50, "keyWord": "", "projectType": "",
                }, form=True))
                if response.get("status") != "ok":
                    raise SourceError("百度分页接口未向匿名请求开放；只导入官网公开首屏")
                data = response["data"]
                count, batch = int(data["total"]), data["list"]
                if int(data["pageNum"]) != page or not isinstance(batch, list) or expected not in (None, count):
                    break
                expected = count
                pages.extend(batch)
                if len(pages) >= count or not batch:
                    break
            return self.snapshot(pages or rows, expected is not None and len(pages) == expected)
        except (KeyError, TypeError, ValueError) as exc:
            snapshot = self.snapshot(rows, False)
            snapshot.notice = str(exc) if isinstance(exc, SourceError) else "百度公开分页结构变化；只导入官网公开首屏"
            return snapshot
