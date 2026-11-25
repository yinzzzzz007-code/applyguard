import unittest
import base64
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from backend.services.evidence_scope import matches_item
from backend.services.resume_draft_vault import _claim_text
from backend.services.structured_verifier import guard_cited_verdict
from backend.services import evidence_workspace as workspace
from backend.services.local_store import save_resume_draft
from backend.services.grounded_workflow import load_grounding_experiences
from backend.services.resume_sections import sections, education


class OCRIdentityTests(unittest.TestCase):
    def test_ocr_prefix_does_not_hide_education_heading(self):
        rows=sections('已教育背景\n清华大学，计算机科学\n上海交通大学，软件工程\n')
        self.assertEqual(len(education(rows[0][1])),2)

    def test_manual_association_requires_explicit_confirmation_and_is_not_a_verdict(self):
        form={'candidateId':'cand_test','basic':{},'projects':[{'id':'p1','title':'SQL Copilot',
              'description':'Built a SQL assistant with Spider evaluation.'}],'internships':[],'education':[],'awards':[],'extras':{}}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'APPLYGUARD_LOCAL_DIR':directory,'APPLYGUARD_EVIDENCE_DIR':directory}):
            save_resume_draft(form)
            ws=workspace.create_workspace('test')
            encoded=base64.b64encode('# 自然语言查询助手\nSpider 评测准确率为 87%。'.encode()).decode()
            row=workspace.import_files(ws['workspace_id'],[{'relative_path':'README.md','content_base64':encoded}])['files'][0]
            workspace.review_evidence(row['evidence_id'],{'normalized_fields':{},'review_state':'REVIEWED'})
            link={'target_type':'project','target_id':'p1','evidence_id':row['evidence_id']}
            with self.assertRaisesRegex(ValueError, '无法自动确认'):
                workspace.create_link(link)
            created=workspace.create_link({**link,'association_confirmed':True})
            self.assertTrue(created['association_confirmed'])
            self.assertEqual(workspace.list_links()['links'][0]['association_confirmed'],1)
            items=load_grounding_experiences(Path(directory)/'unused.json',{'candidate_id':'cand_test','resume_draft':form})
            self.assertEqual(len(items[0]['evidence_sources']),1)
            self.assertIn('87%',items[0]['evidence_sources'][0]['description'])

    def test_long_project_draft_does_not_only_keep_the_title(self):
        source = '项目标题\n负责训练与评测，使用少于500万条数据。\n' + '补充说明。' * 100
        result = _claim_text('', '项目标题', '', source)
        self.assertIn('少于500万条', result)
        self.assertLessEqual(len(result), 420)

    def test_title_can_include_prefix_and_suffix(self):
        self.assertTrue(matches_item('基于Llama3的轻量大语言模型训练与对齐系统', 'README.md',
                                    '# 轻量大语言模型训练与对齐\n项目说明'))

    def test_common_technologies_do_not_bind_another_project(self):
        self.assertFalse(matches_item('ActionPersona', 'README.md',
                                     '# Finbot\n使用 Python 和 Agent 开展大模型训练。',
                                     description='使用 Python 和 Agent 开展大模型训练。'))

    def test_explicit_technical_denial_remains_visible_for_review(self):
        verdict = guard_cited_verdict('完成了GQA注意力模块的开发。', {
            'relation':'CONTRADICTED',
            'reason':'DRAFT[完成GQA注意力模块的开发] SOURCE[该演示版本不使用分组查询注意力（GQA）]',
            'citations':[{'quote':'该演示版本不使用分组查询注意力（GQA）'}],
        })
        self.assertEqual(verdict['relation'], 'INSUFFICIENT')
        self.assertIn('可能存在冲突', verdict['reason'])

    def test_cpu_metric_difference_has_a_readable_warning(self):
        verdict = guard_cited_verdict('峰值CPU使用率从95%降低至50%。', {
            'relation':'CONTRADICTED', 'reason':'DRAFT[不同说法] SOURCE[峰值 CPU 使用率从 95% 降至 60%]',
            'citations':[{'quote':'峰值 CPU 使用率从 95% 降至 60%'}],
        })
        self.assertEqual(verdict['relation'], 'INSUFFICIENT')
        self.assertIn('相近指标数值不同', verdict['reason'])
