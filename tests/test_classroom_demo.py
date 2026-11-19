import os
import tempfile
import unittest
from unittest.mock import patch

from backend.app import build_mock_workflow
from backend.services import classroom_demo, evidence_workspace, job_radar, local_store


class ClassroomDemoTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        env = patch.dict(os.environ, {
            "APPLYGUARD_LOCAL_DIR": folder.name + "/drafts",
            "APPLYGUARD_EVIDENCE_DIR": folder.name + "/evidence",
        })
        env.start()
        self.addCleanup(env.stop)

    def test_complete_sample_is_saved_once_and_can_be_restored(self):
        classroom_demo.load_demo(build_mock_workflow)
        saved = local_store.load_workflow_draft()
        self.assertFalse(saved["stale"])
        self.assertTrue(saved["workflow"]["resume_claims"])
        self.assertEqual(saved["form"]["education"][0]["school"], "华南理工大学")
        self.assertEqual(len(saved["form"]["projects"]), 2)
        workspace, = evidence_workspace.list_workspaces()
        self.assertEqual(len(evidence_workspace.list_files(workspace["workspace_id"])), 2)
        self.assertEqual(job_radar.list_jobs("/api/v1/jobs")["total"], 1)
        classroom_demo.load_demo(build_mock_workflow)
        self.assertEqual(local_store.load_workflow_draft()["saved_at"], saved["saved_at"])

    def test_personal_resume_is_not_replaced(self):
        local_store.save_resume_draft({"candidateId": "cand_personal", "basic": {}})
        with self.assertRaisesRegex(ValueError, "已有个人经历"):
            classroom_demo.load_demo(build_mock_workflow)
        self.assertEqual(local_store.load_resume_draft()["candidateId"], "cand_personal")
        self.assertIsNone(local_store.load_workflow_draft())
