"""Regression for the Chinese internship JD used in the offline demo."""

import unittest

from backend.app import build_mock_workflow
from backend.services.jd_parser import JDParser


JD = """多模态评测研发实习生实习
2028届及以后毕业的在校生
工作职责
职位描述：我们正在招聘多模态评测研发实习生，参与内部评测平台建设。
一、模型能力评估
1. 接入 Benchmark 并维护评测数据；
2. 清理数据集并检查质量检查结果；
3. 跟踪不同 Checkpoint 的模型评测表现；
二、自动化研发
1. 开发 LLM Harness 与 Eval Workflow；
2. 适配推理引擎并优化并发能力；
任职要求
1. 本科在读，熟悉 Python；
2. 了解预训练和多模态技术；
3. 能连续实习 3 个月。
加分项
- 接触过 PyTorch 或 vLLM；
- 了解 AI Infra 或后端开发。
面向对象
2028届及以后毕业的在校生"""


class ChineseOfflineJDTests(unittest.TestCase):
    def test_single_line_demo_title_and_bonus_are_separate(self) -> None:
        text = "后端开发实习生。岗位职责：使用 Python 编写接口服务、补充自动化测试，并使用版本协作。加分项：有数据处理相关项目经验。"
        parsed, _, _ = JDParser(None).parse(text)
        self.assertEqual(parsed["title"], "后端开发实习生")
        self.assertEqual(len(parsed["requirements"]), 4)
        self.assertFalse(any(item["text"] == parsed["title"] for item in parsed["requirements"]))
        self.assertEqual([item["type"] for item in parsed["requirements"]], ["HARD", "HARD", "HARD", "PREFERRED"])

    def test_offline_result_preserves_title_and_grounded_requirements(self):
        parsed, mode, failure = JDParser().parse(JD)
        self.assertEqual((mode, failure), ("RULE_FALLBACK", None))
        self.assertEqual(parsed["title"], "多模态评测研发实习生")
        self.assertEqual(parsed["company"], "UNKNOWN")
        self.assertGreater(len(parsed["requirements"]), 5)
        self.assertTrue(all(item["evidence_text"] in JD for item in parsed["requirements"]))
        texts = [item["text"] for item in parsed["requirements"]]
        self.assertNotIn("多模态评测研发实习生实习", texts)
        self.assertEqual(sum("2028届" in text for text in texts), 1)
        self.assertFalse(any(text.startswith(("一、", "二、", "职位描述：")) for text in texts))

    def test_offline_workflow_reports_requested_mode_without_model_failure(self):
        result = build_mock_workflow({"candidate_id": "cand_demo_001", "jd_text": JD, "parse_mode": "offline"})
        self.assertEqual(result["component_modes"]["requested_parse_mode"], "OFFLINE")
        self.assertFalse(result["step_trace"][1].get("fallback_reason"))

    def test_model_paraphrase_uses_exact_quote_without_accepting_invented_skill(self):
        source = "大模型评测实习生\n任职要求\n熟悉 Python，具备良好的编程习惯和基础工程能力。"
        quote = "熟悉 Python，具备良好的编程习惯和基础工程能力"

        class FakeModel:
            def __init__(self, term):
                self.term = term

            def complete_json(self, *_):
                return {"title": "大模型评测实习生", "company": "UNKNOWN", "requirements": [
                    {"text": "具备 Python 开发能力", "type": "HARD", "category": "SKILL",
                     "normalized_terms": [self.term], "evidence_text": quote, "confidence": 0.9}
                ]}

        parsed, mode, failure = JDParser(FakeModel("Python")).parse(source)
        self.assertEqual((mode, failure), ("MODEL_SPAN_REPAIRED", None))
        self.assertEqual(parsed["requirements"][0]["text"], quote)
        self.assertLessEqual(parsed["requirements"][0]["confidence"], 0.7)
        _, rejected_mode, rejected_reason = JDParser(FakeModel("CUDA")).parse(source)
        self.assertEqual(rejected_mode, "RULE_FALLBACK")
        self.assertIn("not grounded", rejected_reason)


if __name__ == "__main__":
    unittest.main()
