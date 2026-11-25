"""Run offline regression checks for the desktop discovery and OCR changes."""
from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
os.environ.setdefault('APPLYGUARD_OCR_BACKEND', 'rapidocr')
tests = [
    'tests.test_agent_experience_suggestions',
    'tests.test_model_settings',
    'tests.test_ocr_compact_projects',
    'tests.test_docx_extract',
    'tests.test_evidence_ocr_identity',
    'tests.test_evidence_scope_regressions',
    'tests.test_resume_draft_vault',
    'tests.test_resume_sections',
    'tests.test_resume_abnormal',
    'tests.test_folder_picker',
    'tests.test_agent_bridge',
    'tests.test_material_discovery',
    'tests.test_sag_storage',
    'tests.test_verification_failures',
    'tests.test_runtime_logging',
    'tests.test_counterevidence_anchors',
    'tests.test_export_conflict_preflight',
    'tests.test_harness_process',
    'tests.test_evidence_workspace',
    'tests.test_evidence_field_checks',
    'tests.test_polish_navigation',
    'tests.test_agent_mcp',
    'tests.test_harness_setup',
    'tests.test_github_discovery',
    'tests.test_review_export',
    'tests.test_grounding_v2',
    'tests.test_grounding_scope',
]
result = subprocess.run([sys.executable, '-m', 'unittest', *tests], cwd=root)
raise SystemExit(result.returncode)
