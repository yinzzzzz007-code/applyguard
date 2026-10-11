"""Resume draft → workflow experiences."""

from __future__ import annotations

import unittest

from backend.services.resume_draft_vault import experiences_from_resume_draft
from backend.services.schema_validation import validate_contract


class ResumeDraftVaultTests(unittest.TestCase):
    def test_builds_claims_from_internships_and_awards(self) -> None:
        form = {
            "candidateId": "cand_demo_001",
            "internships": [
                {
                    "id": "internship_yixun",
                    "organization": "广东亿迅科技有限公司",
                    "title": "后端开发实习生",
                    "role": "实习生",
                    "start": "2025-07",
                    "end": "2025-09",
                    "description": "参与内部平台接口开发，编写单元测试。",
                }
            ],
            "projects": [],
            "awards": [
                {
                    "id": "award_1",
                    "name": "校级程序设计竞赛二等奖",
                    "issuer": "学生会",
                    "date": "2025-11",
                    "description": "",
                }
            ],
        }
        items = experiences_from_resume_draft(form)
        self.assertEqual(len(items), 2)
        for item in items:
            validate_contract("experience", item)
        texts = {c["text"] for exp in items for c in exp["claims"]}
        self.assertTrue(any("亿迅" in t or "接口" in t for t in texts))
        self.assertTrue(any("程序设计" in t for t in texts))
        # Must not look like seed claim ids
        claim_ids = {c["claim_id"] for exp in items for c in exp["claims"]}
        self.assertFalse(any("lora" in cid or "pipeline" in cid for cid in claim_ids))


if __name__ == "__main__":
    unittest.main()
