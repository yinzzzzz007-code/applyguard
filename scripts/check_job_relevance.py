"""Offline end-to-end replay for CV import, job discovery, and radar ordering."""
import argparse
import base64
import hashlib
import json
import re
import sqlite3
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.jd_parser import JDParser
from backend.services.jd_match_scope import select_requirements_for_matching
from backend.services.resume_draft_vault import experiences_from_resume_draft
from backend.services.resume_parser import parse_resume_pdf

SEED = ROOT / "tests/fixtures/seed-code-agent-zh.txt"
PROBES = {
    "后训练": "熟悉大模型后训练、强化学习和训练数据构建",
    "量化研究": "使用 Python 分析金融数据，开展投资组合、估值与回测研究",
    "检索增强": "开发 RAG 检索增强系统，评估问答效果",
    "软件开发": "使用 TypeScript、Java、Python 等语言开发应用并测试",
    "推理优化": "针对 GPU、CUDA 或分布式训练开展性能优化与评测",
    "训练框架": "熟练使用 PyTorch/TensorFlow/JAX 等任一深度学习框架",
}
# One preselected, visually checked association per source file. IDs refer to the supplied screenshots.
EXPECTED = {
    "01_21885a24": ("推理优化", ["分布式", "gpu"]),
    "02_c552562e": ("量化研究", ["blackrock", "black rock", "bond pricing"]),
    "03_58ab22ae": ("后训练", ["innovator", "gspo"]),
    "04_41219d2a": ("软件开发", ["agentic", "becton", "coachwell"]),
    "05_db862d99": ("后训练", ["llama", "grpo"]),
    "06_7640c99a": ("检索增强", ["clinicdesk","房租","租赁"]),
    "07_d33d9d88": ("检索增强", ["multiagentresearch","documentintelligence","airesearchassistant"]),
    "08_58323ec5": ("后训练", ["qwen","algorithmengineer","lora"]),
    "09_f3a87c0b": ("检索增强", ["graduateschool","multiagentqa","bm25"]),
    "10_cc67440e": ("软件开发", ["tensorflow","bert","mockedbitcoin"]),
    "11_e26c6ac3": ("软件开发", ["electronicscompany","ticketprice","gymreservation"]),
    "12_82b2df82": ("推理优化", ["tensor processing","tensorflow","google"]),
    "13_61a5976a": ("软件开发", ["microsoft","primewardrobe","amazon"]),
    "14_e8fedd4d": ("推理优化", ["nano","gemm","quwen","qwen"]),
    "merged-8-9": ("检索增强", ["graduateschool","bm25"]),
}


# Prespecified from the CV and JD. Each row identifies a project, a source clause and acceptable status.
SEED_CHECKS = (
    ("Nemotron", "预训练与后训练优化", {"direct"}),
    ("Nemotron", "熟悉大模型或RL", {"direct"}),
    ("Nemotron", "任一深度学习框架", {"framework"}),
    ("Multi-Agent PPO", "熟悉大模型或RL", {"direct"}),
    ("SocialMimic", "真实软件工程场景的评测体系", {"related"}),
    ("RouteKV", "出色的问题分析", {"direct", "related"}),
    ("RouteKV", "真实软件工程场景的评测体系", {"related"}),
)
SEED_CONTROLS = (
    ("FinBot", "任一深度学习框架", {"no_project_signal"}),
    ("SocialMimic", "任一深度学习框架", {"no_project_signal"}),
    ("SocialMimic", "负责提升Code Agent", {"no_project_signal", "related"}),
    ("Nemotron", "真实软件工程场景的评测体系", {"related"}),
    ("RouteKV", "主导过有影响力的项目", {"related"}),
)

def labeled_cases(traces, cases):
    rows = []
    for project, clause, expected in cases:
        observed = sorted({t["result"] for t in traces if project.casefold() in t["project"].casefold()
                           and clause in t["requirement"] and t["group"] == "projects"})
        rows.append({"project": project, "clause": clause, "expected": sorted(expected),
                     "observed": observed, "pass": bool(observed) and set(observed) <= expected})
    return rows

def sha(data):
    return hashlib.sha256(data).hexdigest()

def compact(text):
    return re.sub(r"[\W_]+", "", text.casefold())

def imported(path):
    data = path.read_bytes()
    result = parse_resume_pdf(base64.b64encode(data).decode(), path.name, parse_mode="offline")
    form = result["form"]
    for group in ("projects", "internships", "awards", "education"):
        for index, row in enumerate(form.get(group, [])):
            row.setdefault("id", f"{group}_{index}")
    return result, experiences_from_resume_draft(form)

def evaluate(parsed, items):
    return EvidenceMatcher().match(parsed, items)["matches"] if items else []

def collection(directory, filenames=()):
    from pypdf import PdfReader
    probes = {k: JDParser().parse("测试岗位\n任职要求\n" + v)[0] for k,v in PROBES.items()}
    results = []
    paths = sorted(directory.rglob("*.pdf"))
    if filenames:
        wanted = set(filenames)
        paths = [p for p in paths if p.name in wanted]
        missing = wanted - {p.name for p in paths}
        if missing:
            raise ValueError("PDF not found: " + ", ".join(sorted(missing)))
    for path in paths:
        row = {"file":path.name, "sha256":sha(path.read_bytes())}
        try:
            reader = PdfReader(BytesIO(path.read_bytes()))
            row["pages"] = len(reader.pages)
            row["image_pages"] = sum(not (p.extract_text() or "").strip() for p in reader.pages)
            row["page_fingerprints"] = [sha((p.extract_text() or "").encode() + b"".join(i.data for i in p.images)) for p in reader.pages]
            output, items = imported(path)
            row.update(characters=output["char_count"], projects=len(output["form"]["projects"]),
                       internships=len(output["form"]["internships"]), extractor=output["extractor"])
            index = {i["experience_id"]:i for i in items}
            row["related_experiences"] = {}
            row["negative_checks"] = []
            expectation = next((v for key,v in EXPECTED.items() if path.stem.startswith(key)), None)
            for role, parsed in probes.items():
                matches = evaluate(parsed, items)
                row["related_experiences"][role] = len({m["experience_id"] for m in matches})
                if role == "量化研究" and path.stem.startswith(("05_db862d99", "06_7640c99a", "14_e8fedd4d")):
                    row["negative_checks"].append({"role":role, "expected":"no_financial_research",
                                                   "passed":not matches, "unexpected_projects":len(matches)})
                if expectation and role == expectation[0]:
                    def contains(text):
                        return any(compact(term) in compact(text) for term in expectation[1])
                    def item_contains(item):
                        return contains(" ".join([item.get("title",""), *item.get("responsibilities",[])]))
                    available = {i for i,v in index.items() if item_contains(v)}
                    linked = [m for m in matches if m["experience_id"] in available]
                    row["check"] = {"role":role, "anchors":expectation[1],"source_found":contains(output["source_text"]),
                                    "in_library":bool(available), "retrieved":bool(linked),
                                    "stage":"matched" if linked else "matcher" if available else
                                    "import_section" if contains(output["source_text"]) else "ocr_or_transcription"}
        except Exception as error:
            row["error"] = str(error)[:300]
        results.append(row)
        print(path.name, row.get("check",{}).get("stage",row.get("error","unlabelled")), flush=True)
    return results

def seed_case(cv, jd_file):
    jd = jd_file.read_text(encoding="utf-8").strip()
    source, items = imported(cv)
    parsed = JDParser().parse(jd)[0]
    scoped = select_requirements_for_matching(parsed)
    matches = evaluate(parsed, items)
    project_ids = {"exp_" + row["id"].removeprefix("exp_") for row in source["form"]["projects"]}
    traces = []
    for req in scoped:
        subset = {m["experience_id"]:m for m in matches if m["requirement_id"]==req["requirement_id"]}
        for exp in items:
            match = subset.get(exp["experience_id"])
            lead = (match or {}).get("lead") or {}
            traces.append({"requirement":req["text"], "section":req.get("section"), "project":exp["title"],
                           "result":lead.get("kind", "literal" if match else "no_project_signal"),
                           "group":"projects" if exp["experience_id"] in project_ids else "other",
                           "matched_terms":lead.get("terms", []), "pending_context":lead.get("pending_context", [])})
    return source["form"], {"cv_sha256":sha(cv.read_bytes()), "jd_sha256":sha(jd.encode()),
                           "project_count":len(source["form"]["projects"]),"duties":sum(r.get("section")=="description" for r in scoped),
                           "requirements":len(scoped),"matches":len(matches),"positives":labeled_cases(traces, SEED_CHECKS),
                           "controls":labeled_cases(traces, SEED_CONTROLS),"pairs":traces}

def radar(form, db_path):
    from backend.services import job_radar, job_recommendation as rec
    with sqlite3.connect(db_path.resolve().as_uri()+"?mode=ro",uri=True) as conn:
        conn.row_factory=sqlite3.Row
        jobs=[job_radar._view(row) for row in conn.execute(job_radar.JOB_WITH_UNREAD)]
    for job in jobs:
        job_radar._apply_current_match(job, form)
    def order():
        return [j["title"] for j in sorted(jobs,key=lambda j:j["recommendation_rank"])]
    rec.decorate(jobs,form,{})
    initial=order()
    scores=rec.semantic_scores(rec.profile_texts(form), jobs)
    rec.decorate(jobs,form,{},scores)
    return {"count":len(jobs), "jobs_sha256":sha(json.dumps(sorted((j["id"],j.get("description"),j.get("requirements")) for j in jobs),ensure_ascii=False).encode()),
            "pending":initial, "ready":order(),
            "top10":[{"id":j["id"], "title":j["title"], "score":j["recommendation_score"],
                      "reasons":j["recommendation_reasons"]}
                     for j in sorted(jobs,key=lambda x:x["recommendation_rank"])[:10]]}

def main():
    cfg=argparse.ArgumentParser(description=__doc__)
    cfg.add_argument("--cv",type=Path)
    cfg.add_argument("--jd",type=Path,default=SEED)
    cfg.add_argument("--jobs",type=Path)
    cfg.add_argument("--collection",type=Path)
    cfg.add_argument("--only", nargs="+", help="Retest the named files under --collection")
    cfg.add_argument("--radar-cvs", nargs="+", type=Path, help="Compare multiple local PDFs against the same --jobs snapshot")
    cfg.add_argument("--report",type=Path,required=True)
    args=cfg.parse_args()
    if args.only and not args.collection:
        cfg.error("--only requires --collection")
    if args.radar_cvs and not args.jobs:
        cfg.error("--radar-cvs requires --jobs")
    if not args.collection and not args.cv and not args.radar_cvs:
        cfg.error("supply --cv or --collection")
    report={}
    if args.cv:
        form, report["seed"]=seed_case(args.cv,args.jd)
        if args.jobs:
            report["radar"]=radar(form,args.jobs)
    if args.radar_cvs:
        report["profiles"] = []
        for path in args.radar_cvs:
            output, _ = imported(path)
            result = radar(output["form"], args.jobs)
            report["profiles"].append({"file":path.name, "cv_sha256":sha(path.read_bytes()), **result})
            print(path.name, "ranked", result["count"], flush=True)
    if args.collection:
        report["collection"]=collection(args.collection, args.only)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(args.report)

if __name__=="__main__":
    main()
