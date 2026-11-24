"""Regressions for duty retrieval and source-grounded clarification."""
import unittest
from pathlib import Path

from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.experience_relevance import discovery
from backend.services.job_capabilities import structure
from backend.services.job_fit import compare, job_sections
from backend.services.jd_parser import JDParser
from backend.services.resume_draft_vault import experiences_from_resume_draft


class JobRelevanceTests(unittest.TestCase):
    def test_seed_units_and_exact_quotes(self):
        source = (Path(__file__).parent / "fixtures" / "seed-code-agent-zh.txt").read_text(encoding="utf8")
        parsed, _, _ = JDParser().parse(source)
        units = parsed["requirements"]
        self.assertEqual(sum(r.get("section") == "description" for r in units), 4)
        self.assertTrue(all(r["evidence_text"] in source for r in units))
        self.assertFalse(any("50 个应用" in r["text"] or "实验室和岗位" in r["text"] for r in units))
        opts = next(r for r in units if r["alternatives"])
        self.assertEqual(set(opts["alternatives"]), {"PyTorch", "TensorFlow", "JAX"})
        self.assertEqual(opts["priority"], "core")
        self.assertEqual(next(r for r in units if "数据结构" in r["text"])["priority"], "general")

    def test_shared_python_does_not_establish_quantitative_research(self):
        ask = {"category":"SKILL", "text":"使用 Python 分析金融数据，开展投资组合估值与回测"}
        self.assertIsNone(discovery(ask, {"title":"推理优化", "summary":"使用 Python 开发推理引擎。"}))
        positive = discovery(ask, {"title":"固收实习", "summary":"用 Python 研究债券信用利差。"})
        self.assertEqual(positive["kind"], "direct")

    def test_project_topic_does_not_establish_leadership_or_software_context(self):
        project = {"title":"模型实验", "summary":"在大模型上完成评测。针对错误样本优化训练数据。"}
        def assess(phrase):
            return discovery({"category":"SKILL", "text":phrase}, project)
        impact = assess("在大模型领域，主导过有影响力的项目或论文者优先")
        self.assertEqual(impact["kind"], "related")
        self.assertIn("本人主导的具体工作", impact["pending_context"])
        self.assertIn("项目或论文的实际影响", impact["pending_context"])
        self.assertIn("真实软件工程任务场景", assess("构建面向真实软件工程场景的评测体系与数据回流")["pending_context"])
        project["summary"] = "为 SWE-bench 真实软件工程任务搭建评测体系。"
        self.assertEqual(assess("构建面向真实软件工程场景的评测体系")["kind"], "direct")

    def test_alternatives_long_text_and_all_candidates(self):
        source = "算法岗\n岗位职责：负责系统评测和推理优化。\n任职要求：熟练使用PyTorch/TensorFlow/JAX等任一深度学习框架。"
        parsed = structure({"source_text":source,"requirements":[],"jd_id":"jd_test"}, lambda _:False)
        framework = parsed["requirements"][-1]
        rows = [{"id":str(i), "title":"工程项目 "+str(i), "description":body}
                for i,body in enumerate(["早期工作。"*100+"\n后期使用 LoRA 进行 SFT。",
                                          "使用 JAX 训练网络。","只调用外部模型 API 生成摘要。",
                                          "实现 PyTorch 模型。","在 TensorFlow 中完成实验。"])]
        exps = experiences_from_resume_draft({"candidateId":"cand_test", "projects":rows})
        hits = [discovery(framework, x) for x in exps]
        self.assertEqual([h and h["kind"] for h in hits], ["framework","direct",None,"direct","direct"])
        self.assertIn("SFT", hits[0]["quote"])
        self.assertEqual(hits[1]["terms"], ["JAX"])
        results = EvidenceMatcher().match(parsed, exps)
        scoped = [r for r in results["matches"] if r["requirement_id"] == framework["requirement_id"]]
        self.assertEqual(len(scoped), 4)
        self.assertFalse(any(r["ready_for_selection"] for r in scoped))

    def test_interdisciplinary_model_work_and_classical_materials(self):
        profile = (("研究项目", "构建训练数据并使用 PyTorch 微调神经网络，开展留出评测。"),)
        jobs = [
            {"title":"材料工程师", "responsibilities":"负责高分子加工与复合材料力学仿真。", "requirements":"Python 和团队合作优先。"},
            {"title":"材料机器学习工程师", "responsibilities":"负责材料机器学习模型训练和评测。", "requirements":"熟悉 PyTorch 框架。"},
        ]
        self.assertGreater(compare(jobs[1]["title"],job_sections(jobs[1]),profile)[0],
                           compare(jobs[0]["title"],job_sections(jobs[0]),profile)[0])



    def test_vector_cache_is_independent_of_cobatched_jobs(self):
        from unittest.mock import patch
        from backend.services import job_recommendation as rec
        from backend.services.local_sag_embedding import LocalMiniLM
        def encode(batch):
            return [[len(batch),len(s)] for s in batch]
        with patch.object(LocalMiniLM, "_embed", side_effect=encode), patch.object(rec, "_VECTORS", rec.OrderedDict()):
            first = rec.vectorize(["short", "a longer job", "short"])
            rec._VECTORS.clear()
            self.assertEqual(first[0], rec.vectorize(["short"])[0])
            self.assertEqual(first[0], first[2])

    def test_pending_refresh_preserves_last_completed_order_scores_and_reasons(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from backend.services import job_recommendation as rec
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in ("model_quantized.onnx", "tokenizer.json"):
                (directory / name).touch()
            resume = {"projects": [{"title": "RAG 系统", "description": "负责向量检索"}]}
            jobs = [{"id": "first", "title": "检索增强工程师"}, {"id": "second", "title": "数据工程师"}]
            with patch.object(rec, "locations", return_value=(directory, directory)), \
                 patch.object(rec.threading.Thread, "start"), \
                 patch.object(rec, "_STATES", rec.OrderedDict()), patch.object(rec, "_COMPLETED", rec.OrderedDict()):
                self.assertEqual(rec.rank_jobs(jobs, resume, {})["state"], "loading")
                state = next(iter(rec._STATES.values()))
                state.update(state="ready", scores={j["id"]: {"semantic":85, "affinity":0, "aversion":0} for j in jobs})
                self.assertEqual(rec.rank_jobs(jobs, resume, {})["state"], "ready")
                snapshot = [(j["recommendation_rank"], j["recommendation_score"], j["recommendation_reasons"]) for j in jobs]
                jobs.append({"id": "fresh", "title": "机器学习研发"})
                self.assertEqual(rec.rank_jobs(jobs, resume, {})["state"], "loading")
                self.assertEqual(snapshot, [(j["recommendation_rank"], j["recommendation_score"], j["recommendation_reasons"]) for j in jobs[:2]])
                self.assertGreater(jobs[-1]["recommendation_rank"], max(r[0] for r in snapshot))

    def test_employer_and_role_stay_with_work_across_lines(self):
        from backend.services.resume_sections import project_entries
        rows = project_entries(["Example Labs", "Mountain View, CA", "Software Engineer Intern", "Built a reporting service."], "internships")
        self.assertEqual(len(rows), 1)
        self.assertIn("Software Engineer Intern", rows[0]["description"])
        self.assertIn("Built a reporting service", rows[0]["description"])

    def test_english_continuation_starts_at_a_named_project(self):
        from backend.services.resume_sections import sections
        raw = "A bullet continuing from the first page.\nIndividual Project, Search Assistant\nBuilt a retriever.\nEXCHANGE EXPERIENCE\nVisited a lab."
        self.assertEqual(sections(raw), [("projects", ["Individual Project, Search Assistant", "Built a retriever."]),
                                         ("other", ["Visited a lab."])])

if __name__ == "__main__":
    unittest.main()
