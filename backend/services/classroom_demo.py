"""Prepare a repeatable classroom application from bundled sample data."""
import base64
import json
import threading
from pathlib import Path

from backend.services import evidence_workspace, job_radar, local_store

_APPLICATION = "app_classroom_sample"
_TEMPLATE = Path(__file__).resolve().parents[2] / "frontend/public/data/resume-template.example.json"
_WORKSPACE = "课堂示例材料"
_LOCK = threading.Lock()
_JOB = {
    "title": "大模型应用开发实习生",
    "company": "课程项目组",
    "source_kind": "fictional_example",
    "source_namespace": "applyguard-classroom",
    "external_id": "llm-application-intern",
    "status": "unknown",
    "description": (
        "岗位职责：参与大语言模型实验和开发工具维护。\n"
        "任职要求：\n1. 熟悉 Python 和 PyTorch。\n2. 有 LoRA 微调或 SFT 训练经验。\n"
        "3. 有工具调用或代码检索项目经验。\n加分项：了解 DPO 偏好对齐与测试验证。"
    ),
}


def load_demo(run_workflow):
    with _LOCK:
        template = json.loads(_TEMPLATE.read_text(encoding="utf-8"))
        resume = local_store.load_resume_draft()
        existing = local_store.load_workflow_draft()
        if resume and any(resume.get(key) != value for key, value in template.items() if key != "dirty"):
            raise ValueError("已有个人经历。请在空白工作区体验课堂示例。")
        if existing:
            if existing["workflow"]["application_id"] == _APPLICATION:
                return {"saved": True}
            raise ValueError("已有申请草稿。请在空白工作区体验课堂示例。")
        if not resume:
            saved = local_store.save_resume_draft({"form": template, "expected_saved_at": None})
            resume = {**template, "savedAt": saved["saved_at"]}
        workspace = next((item for item in evidence_workspace.list_workspaces() if item["name"] == _WORKSPACE), None)
        if workspace is None:
            workspace = evidence_workspace.create_workspace(_WORKSPACE)
        for project in template["projects"]:
            content = f"# 课堂示例项目记录\n\n项目名称：{project['title']}\n\n{project['description']}\n"
            result = evidence_workspace.import_files(workspace["workspace_id"], [{
                "relative_path": project["title"] + ".md",
                "content_base64": base64.b64encode(content.encode()).decode(),
            }])["files"][0]
            evidence_id = result.get("evidence_id")
            if not evidence_id:
                raise ValueError("示例材料导入失败，请重试。")
            evidence_workspace.review_evidence(evidence_id, {"normalized_fields": {}, "review_state": "REVIEWED"})
            evidence_workspace.create_link({"target_type": "project", "target_id": project["id"], "evidence_id": evidence_id})
        job = job_radar.save_jobs([_JOB])["items"][0]
        job_radar.set_stage(job["id"], "preparing")
        jd = job["workflow_jd_text"]
        workflow = run_workflow({"candidate_id": resume["candidateId"], "application_id": _APPLICATION,
                                 "resume_draft": resume, "jd_text": jd, "target_job": job, "parse_mode": "offline"})
        local_store.save_workflow_draft({"workflow": workflow, "jd": jd, "form": resume,
                                         "active_job_id": job["id"], "job_content_hash": job["content_hash"]})
        return {"saved": True}
