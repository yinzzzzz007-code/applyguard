"""Evidence matching uses 任职要求 and 加分项, not 职位描述."""

import unittest

from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.jd_match_scope import qualification_spans, select_requirements_for_matching
from backend.services.jd_parser import JDParser
from tests.test_jd_chinese_offline import JD


class MatchScopeTests(unittest.TestCase):
    def test_chinese_jd_keeps_requirements_and_bonus_only(self):
        parsed, mode, failure = JDParser().parse(JD)
        self.assertEqual((mode, failure), ("RULE_FALLBACK", None))
        scoped = select_requirements_for_matching(parsed)
        scoped_text = "\n".join(item["evidence_text"] for item in scoped)
        parsed_text = "\n".join(item["evidence_text"] for item in parsed["requirements"])

        self.assertIn("熟悉 Python", scoped_text)
        self.assertTrue("PyTorch" in scoped_text or "vLLM" in scoped_text)
        self.assertIn("Public Benchmark", parsed_text)
        self.assertNotIn("Public Benchmark", scoped_text)
        self.assertNotIn("LLM Harness", scoped_text)
        self.assertEqual(len(scoped), 14)
        self.assertFalse(any(item["text"].strip() in {"1.", "2.", "3.", "4.", "5.", "6.", "7."} for item in scoped))
        self.assertLess(len(scoped), len(parsed["requirements"]))
        self.assertTrue(qualification_spans(JD))

    def test_matcher_does_not_score_job_description(self):
        parsed, _, _ = JDParser().parse(JD)
        experience = {
            "candidate_id": "cand_scope",
            "experience_id": "exp_scope",
            "skills": ["Python", "Benchmark"],
            "summary": "",
            "responsibilities": [],
            "title": "",
            "role": "",
            "claims": [],
            "evidence_sources": [],
            "metrics": [],
        }
        result = EvidenceMatcher().match(parsed, [experience])
        considered = {item["requirement_id"] for item in result["matches"]}
        considered.update(item["requirement_id"] for item in result["uncovered_requirements"])
        scoped = {item["requirement_id"] for item in select_requirements_for_matching(parsed)}
        self.assertEqual(considered, scoped)
        described = {
            item["requirement_id"]
            for item in parsed["requirements"]
            if "Public Benchmark" in item["evidence_text"] or "LLM Harness" in item["evidence_text"]
        }
        self.assertTrue(described)
        self.assertTrue(described.isdisjoint(considered))

    def test_english_responsibilities_are_out_of_scope(self):
        source = (
            "Backend Engineer\nRequired:\n本科及以上学历\n3 years of experience\nPython\n"
            "Preferred:\nGit\nResponsibilities:\nMaintain Python APIs"
        )
        parsed, _, _ = JDParser().parse(source)
        scoped = [item["text"] for item in select_requirements_for_matching(parsed)]
        self.assertTrue(any("Python" == text or text == "Python" for text in scoped))
        self.assertTrue(any(text == "Git" for text in scoped))
        self.assertFalse(any("Maintain" in text for text in scoped))

    def test_unsectioned_jd_keeps_every_requirement(self):
        parsed = {
            "source_text": "We are looking for a software engineering intern who can build Python APIs, write automated tests, and collaborate with Git.",
            "requirements": [
                {"requirement_id": "req_python_api", "evidence_text": "can build Python APIs"},
                {"requirement_id": "req_testing", "evidence_text": "write automated tests"},
            ],
        }
        self.assertIsNone(qualification_spans(parsed["source_text"]))
        self.assertEqual(select_requirements_for_matching(parsed), parsed["requirements"])

    def test_description_only_jd_matches_nothing(self):
        source = "后端开发实习生岗位说明如下。\n职位描述\n负责 Python 接口开发和自动化测试，持续维护服务质量。"
        parsed = {
            "source_text": source,
            "requirements": [{
                "requirement_id": "req_api",
                "evidence_text": "负责 Python 接口开发和自动化测试，持续维护服务质量。",
            }],
        }
        self.assertEqual(qualification_spans(source), [])
        self.assertEqual(select_requirements_for_matching(parsed), [])


if __name__ == "__main__":
    unittest.main()
