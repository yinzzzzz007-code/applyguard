"""Regression for the Chinese internship JD used in the offline demo."""

import unittest

from backend.app import build_mock_workflow
from backend.services.jd_parser import JDParser


JD = """大模型预训练评测研发实习生实习
上海、北京
程序&技术类
2027届及之后毕业的在校生
工作职责
职位描述： 我们正在招聘大模型预训练评测研发实习生，共同建设覆盖语言模型与多模态模型的预训练评测体系。你可以根据个人兴趣和能力，重点参与以下一个或多个方向：
一、Benchmark 建设与模型评测
1. 负责 Public Benchmark、In-house Benchmark 及多模态 Benchmark 的调研、接入与维护；
2. 参与评测数据的清洗、格式转换、质量检查和版本管理；
3. 支持预训练模型不同阶段、不同 Checkpoint 的评测，跟踪并分析模型能力变化；
4. 参与模型能力拆解，分析模型的优势、短板、异常表现和能力退化风险；
5. 使用大模型辅助数据处理、评测分析和日常研发，持续提升工作效率；
6. 跟踪业界主流模型、Benchmark 和评测方法，协助完善内部预训练评测体系。
二、评测框架与自动化研发
1. 参与 LLM Harness 及多模态评测框架的设计、开发与维护；
2. 参与 Eval Workflow 建设，推动评测任务编排、执行、监控和结果分析自动化；
3. 参与推理引擎及不同模型架构的适配，支持评测任务稳定、高效运行；
4. 优化评测系统的并发能力、执行效率、稳定性和可扩展性；
5. 建设通用评测工具与基础组件，提高 Benchmark 接入和模型评测效率；
6. 协助定位评测链路中的工程问题，持续改进系统架构和研发体验。
任职要求
1. 本科及以上在读，计算机、人工智能、软件工程或相关专业优先；
2. 熟悉 Python，具备良好的编程习惯和基础工程能力；
3. 对大语言模型、多模态模型及预训练技术感兴趣，了解模型训练与评测的基本流程；
4. 日常能够熟练使用大模型工具，对模型能力边界、优势和短板有一定理解；
5. 认真细致，对数据质量、实验设置和评测结果保持敏感；
6. 具备良好的问题分析能力、学习能力、自驱力和沟通协作能力；
7. 能够保证稳定的实习时间，连续实习 3 个月及以上者优先。
加分项
- 了解大模型预训练流程及常见评测方法；
- 接触过 LLM Eval、开源 Benchmark 或评测框架；
- 有 Benchmark 接入、数据集建设或模型能力分析经验；
- 熟悉多进程、高并发、网络编程、后端开发或软件架构设计；
- 具备 AI Infra 相关项目或实习经验；
- 了解 PyTorch、vLLM 等技术；
- 有多模态模型评测、开源项目、科研或相关工程项目经验。
面向对象
2027届及之后毕业的在校生"""


class ChineseOfflineJDTests(unittest.TestCase):
    def test_offline_result_preserves_title_and_grounded_requirements(self):
        parsed, mode, failure = JDParser().parse(JD)
        self.assertEqual((mode, failure), ("RULE_FALLBACK", None))
        self.assertEqual(parsed["title"], "大模型预训练评测研发实习生")
        self.assertEqual(parsed["company"], "UNKNOWN")
        self.assertGreater(len(parsed["requirements"]), 5)
        self.assertTrue(all(item["evidence_text"] in JD for item in parsed["requirements"]))
        texts = [item["text"] for item in parsed["requirements"]]
        self.assertNotIn("大模型预训练评测研发实习生实习", texts)
        self.assertEqual(sum("2027届" in text for text in texts), 1)
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
