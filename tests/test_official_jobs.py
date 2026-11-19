from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend.services import job_matching, job_radar, job_refresh
from backend.services.job_sources.baidu import Baidu
from backend.services.job_sources.base import Snapshot, SourceError
from backend.services.job_sources.bytedance_seed import BytedanceSeed
from backend.services.job_sources.huawei import Huawei


def sample(key="one", requirements="熟练使用 Python 开发接口服务，能补充自动化测试。"):
    return {
        "external_id": key, "title": "研发实习", "company": "测试公司", "location": "上海",
        "recruitment_type": "日常实习", "url": "https://example.test/jobs/" + key,
        "source_url": "https://example.test/jobs", "status": "open",
        "responsibilities": "参与日常研发工作。", "requirements": requirements,
    }


class AdapterTests(unittest.TestCase):
    def test_baidu_html_and_anonymous_first_page_fallback(self):
        adapter = Baidu()
        job = {"postId": "sample", "name": "研发实习", "workPlace": "上海",
               "serviceCondition": "掌握 Python", "workContent": "参与本地服务开发并补充自动化测试。"}
        html = '<script>window.__INITIAL_DATA__ ={"unused":undefined, "listData":' + json.dumps({
            "total": 2, "listDetailData": [job]}) + '};</script>'
        with patch.object(adapter, "request", side_effect=[html, '{"status":"no-auth"}']):
            result = adapter.fetch()
        self.assertFalse(result.complete)
        self.assertEqual(result.jobs[0]["requirements"], "掌握 Python")
        self.assertTrue(result.jobs[0]["url"].endswith("/jobs/detail/INTERN/sample"))
        with self.assertRaises(SourceError):
            adapter.parse("<html>页面维护</html>")

    def test_huawei_validates_complete_list_and_reads_intentions(self):
        adapter = Huawei()
        rows = [{"advertisementId": 42, "jobId": 5, "jobName": "测试岗位", "workPlace": "广州",
                 "mainBusiness": "请您详见岗位意向中的岗位职责", "jobRequire": "请您详见岗位意向中的岗位要求"}]
        with patch.object(adapter, "api", side_effect=[
            {"result": rows, "pageVO": {"curPage": 1, "totalRows": 1}},
            [{"jobDuty": "参与研发并维护接口服务", "jobRequire": "掌握 Python 与自动化测试"}],
        ]):
            result = adapter.fetch()
        self.assertTrue(result.complete)
        self.assertTrue(result.jobs[0]["details_available"])
        self.assertEqual(result.jobs[0]["requirements"], "掌握 Python 与自动化测试")
        self.assertIn("?advertisementId=42", result.jobs[0]["url"])

    def test_seed_featured_is_partial_and_detail_failure_preserves_good_copy(self):
        adapter = BytedanceSeed()
        key = "1234567890123"
        html = '<script>{"SubJobZh":' + json.dumps({
            "JobName": "测试研发", "JobTypeName": "社招", "City": "北京",
            "ExternalLink": "https://jobs.bytedance.com/experienced/position/" + key + "/detail"}) + '}</script>'
        detail = {"code": 0, "data": {"job_post_detail": {
            "id": key, "title": "测试研发", "description": "开发服务", "requirement": "熟悉 Python 与自动化测试",
            "channel_online_status": 1}}}
        with patch.object(adapter, "request", side_effect=[html, json.dumps(detail)]):
            result = adapter.fetch()
        self.assertFalse(result.complete)
        entry = result.jobs[0]
        adapter.previous = {key: {**entry, "details_available": True, "published_at": ""}}
        with patch.object(adapter, "request", side_effect=[html, SourceError("官网超时")]):
            failed_detail = adapter.fetch()
        self.assertEqual(failed_detail.jobs[0]["requirements"], "熟悉 Python 与自动化测试")
        self.assertTrue(failed_detail.jobs[0]["details_available"])
        self.assertEqual(failed_detail.skipped, 1)

    def test_http_uses_only_allowlisted_hosts(self):
        with self.assertRaises(SourceError):
            Baidu().request("https://example.test/jobs")


class OfficialRefreshTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        env = patch.dict(os.environ, {"APPLYGUARD_LOCAL_DIR": folder.name, "APPLYGUARD_JOB_SOURCES": "baidu,huawei,bytedance_seed",
                                      "APPLYGUARD_JOBS_REFRESH_TIME": "09:00", "APPLYGUARD_JOB_AI_MATCH": "false"})
        env.start()
        self.addCleanup(env.stop)

    @staticmethod
    def refresh(*keys):
        return job_refresh.start(list(keys), force=True, background=False)

    def test_migrate_legacy_db_without_moving_records(self):
        job = job_radar.normalize(sample())
        with closing(sqlite3.connect(self.folder / "job-radar.sqlite3")) as conn, conn:
            conn.execute("""CREATE TABLE opportunities(id TEXT PRIMARY KEY,identity_key TEXT UNIQUE,payload TEXT,
                version INTEGER,stage TEXT,created_at TEXT,imported_at TEXT)""")
            conn.execute("INSERT INTO opportunities VALUES(?, ?, ?, 1, 'preparing', ?, ?)",
                         ("job_1234567890123456", job["identity_key"], json.dumps(job), "old", "old"))
        result = job_radar.get_job("job_1234567890123456")
        self.assertEqual((result["stage"], result["first_seen_at"], result["external_id"]), ("preparing", "old", "one"))
        self.assertIsNone(result["match_level"])

    def test_refresh_dedup_versions_read_and_true_closure(self):
        with patch.object(Baidu, "fetch", return_value=Snapshot([sample()], True)):
            result = self.refresh("baidu")
            self.assertEqual(result["result"]["baidu"]["created"], 1)
            job = job_radar.list_jobs("/api/v1/jobs?source=baidu&new=true&unread=true&city=上海")["items"][0]
            job_radar.handle_post("/api/v1/jobs/alerts/read", {"job_id": job["id"]})
            self.assertEqual(self.refresh("baidu")["result"]["baidu"]["unchanged"], 1)
            self.assertFalse(job_radar.handle_get("/api/v1/jobs/alerts?unread=true")["items"])
        with patch.object(Baidu, "fetch", return_value=Snapshot([sample(requirements="熟悉 PyTorch 和深度学习框架。")], True)):
            self.assertEqual(self.refresh("baidu")["result"]["baidu"]["updated"], 1)
        with patch.object(Baidu, "fetch", return_value=Snapshot([], False)):
            self.assertEqual(self.refresh("baidu")["result"]["baidu"]["closed"], 0)
        with patch.object(Baidu, "fetch", return_value=Snapshot([], True)):
            self.assertEqual(self.refresh("baidu")["result"]["baidu"]["closed"], 1)
        dormant = job_radar.get_job(job["id"])
        self.assertEqual((dormant["status"], dormant["version"], dormant["is_active"]), ("closed", 3, False))
        history = job_radar.handle_get(f"/api/v1/jobs/{job['id']}/versions")["items"]
        self.assertEqual([v["version"] for v in history], [3, 2, 1])
        with self.assertRaisesRegex(ValueError, "已关闭"):
            job_radar.validate_target({"target_job": dormant, "jd_text": dormant["workflow_jd_text"], "resume_draft": {}})
        job_radar.handle_post("/api/v1/jobs/alerts/read-all", {})
        self.assertEqual(job_radar.handle_get("/api/v1/jobs/alerts")["unread"], 0)
        job_radar.handle_post("/api/v1/jobs/alerts/read", {"job_id": job["id"], "unread": True})
        self.assertEqual(job_radar.handle_get("/api/v1/jobs/alerts")["unread"], 3)

    def test_parallel_partial_failure_keeps_jobs_and_source_alert_is_deduped(self):
        with patch.object(Baidu, "fetch", return_value=Snapshot([sample()], True)):
            self.refresh("baidu")
        rendezvous = threading.Barrier(2, timeout=5)
        def fail(_self):
            rendezvous.wait()
            raise SourceError("来源超时")
        def success(_self):
            rendezvous.wait()
            return Snapshot([sample("huawei")], True)
        with patch.object(Baidu, "fetch", fail), patch.object(Huawei, "fetch", success):
            for _ in range(3):
                self.assertEqual(self.refresh("baidu", "huawei")["state"], "partial")
        items = job_radar.list_jobs("/api/v1/jobs?status=open")["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(sum(alert["kind"] == "source_failed" for alert in
                             job_radar.handle_get("/api/v1/jobs/alerts")["items"]), 1)

    def test_duplicate_lease_and_restart_recovery(self):
        time = job_refresh.instant()
        with job_radar.database() as conn:
            conn.execute("INSERT INTO job_refresh_runs(id,state,started_at,lease_until,sources) VALUES(?,'running',?,?,?)",
                         ("lost", job_refresh.stamp(time), job_refresh.stamp(time + job_refresh.LEASE), '["baidu"]'))
        self.assertTrue(job_refresh.start(["huawei"], force=True)["joined"])
        with patch.object(job_refresh, "instant", return_value=time + job_refresh.LEASE + timedelta(seconds=1)):
            self.assertEqual(job_refresh.status()["state"], "interrupted")
            with patch.object(Baidu, "fetch", return_value=Snapshot([sample()], True)):
                self.assertEqual(self.refresh("baidu")["state"], "success")

    def test_observation_updates_without_material_revision(self):
        first = {**sample(), "source_updated_at": "2026-11-18"}
        with patch.object(Baidu, "fetch", return_value=Snapshot([first], True)):
            self.refresh("baidu")
        with patch.object(Baidu, "fetch", return_value=Snapshot([{**first, "source_updated_at": "2026-11-19"}], True)):
            self.assertEqual(self.refresh("baidu")["result"]["baidu"]["unchanged"], 1)
        row = job_radar.list_jobs("/api/v1/jobs")["items"][0]
        self.assertEqual((row["version"], row["source_updated_at"]), (1, "2026-11-19"))
        self.assertEqual(job_radar.handle_get("/api/v1/jobs/alerts")["unread"], 1)

    def test_schedule_disabled_sources_and_local_match(self):
        time = datetime(2026, 11, 18, 0, 30, tzinfo=timezone.utc)
        self.assertEqual(job_refresh.next_refresh(time, 24), "2026-11-18T01:00:00Z")
        job_refresh.configure("huawei", {"enabled": False, "interval_hours": 12})
        self.assertEqual(self.refresh("huawei")["state"], "waiting")
        resume = {"projects": [{"description": "用 Python 开发接口服务与自动化测试"}],
                  "intention": {"expectCity": "上海", "expectRole": "研发实习"}}
        job = job_radar.normalize(sample(), source_id="baidu")
        self.assertEqual(job_matching.match_job(job, resume)["level"], "high")
        self.assertEqual(job_matching.match_job(job, None)["level"], "insufficient")
        self.assertTrue(job_matching.match_job({**job, "education": "硕士"}, resume)["missing"])
        with patch.dict(os.environ, {"APPLYGUARD_JOB_AI_MATCH": "true", "APPLYGUARD_AI_API_KEY": ""}):
            score = job_matching.match_job(job, resume)
            self.assertEqual(job_matching.explain_job(job, score), score)


if __name__ == "__main__":
    unittest.main()
