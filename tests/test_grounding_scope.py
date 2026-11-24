"""SAG checks experience claims only; personal profiles never enter model inputs."""
import copy
import base64
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from backend.services.grounded_workflow import GroundingService, collect_sources
from backend.services.resume_draft_vault import experiences_from_resume_draft
from backend.services.model_client import ModelFailure
from backend.services.grounded_workflow import export_grounded
from backend.services import evidence_workspace as workspace
from tests.test_grounding import AllSources
from tests.test_grounding_v2 import Model


def fixture():
    form = {'candidateId': 'cand_scope',
            'education': [{'id': 'edu', 'school': 'Private School', 'degree': 'BSc', 'major': 'Math'}],
            'internships': [{'id': 'intern', 'organization': 'Lab', 'description': 'Alex wrote Python tests.'}],
            'projects': [{'id': 'project', 'title': 'Atlas', 'description': 'Alex built a Python API.'}],
            'awards': [{'id': 'award', 'name': 'Programming Competition', 'description': 'Alex won a programming prize.'}]}
    return experiences_from_resume_draft(form)


def claims(items):
    return [copy.deepcopy(c) for item in items for c in item['claims']]


def attach_proof(items):
    for item in items[1:]:
        claim = item['claims'][0]
        eid = 'ev_proof_' + claim['claim_id']
        claim['evidence_ids'] = [eid]
        item['evidence_sources'] = [{'evidence_id': eid, 'description': claim['text'],
                                     'verification_status': 'VERIFIED'}]


class GroundingScopeTests(unittest.TestCase):
    def test_personal_only_needs_no_model_or_retriever_even_for_polish(self):
        items = fixture()[:1]
        retriever = MagicMock()
        with patch('backend.services.grounded_workflow.HttpModelClient', side_effect=AssertionError('model forbidden')):
            text, checks, report = GroundingService(retriever=retriever).run(
                claims(items), items, 'cand_scope', 'sag_atomic', polish=True)
        retriever.retrieve_many.assert_not_called()
        self.assertEqual(text[0]['text'], items[0]['claims'][0]['text'])
        self.assertEqual(checks[0]['state'], 'VERIFIED')
        self.assertFalse(checks[0]['grounded'])
        self.assertEqual(checks[0]['support_score'], 0)
        row = report['results'][text[0]['claim_id']]
        self.assertEqual(row['verification_scope'], 'personal')
        self.assertEqual(row['atoms'], [])
        self.assertNotIn('proposed_text', row)
        self.assertEqual(collect_sources(items, 'cand_scope'), ([], {}, {}))

    def test_explicit_rechecks_request_new_model_splits_without_promoting_unlinked_claims(self):
        items = fixture()
        model = MagicMock(wraps=Model())
        service = GroundingService(retriever=MagicMock(), model=model)
        for attempt in range(2):
            _, checks, report = service.run(claims(items), items, 'cand_scope', 'sag_atomic', fresh_atomic=True)
            self.assertIsNone(report['error'])
            self.assertEqual(model.complete_structured.call_count, attempt + 1)
            self.assertNotIn('Private School', model.complete_structured.call_args.args[1])
            for check in checks[1:]:
                row = report['results'][check['claim_id']]
                self.assertEqual(check['state'], 'NEEDS_REVIEW')
                self.assertFalse(check['grounded'])
                self.assertEqual(row['material_status'], 'no_related_material')
                self.assertTrue(row['atoms'])
                for atom in row['atoms']:
                    self.assertEqual(atom['method'], 'model_split_without_sources')
                    self.assertEqual(atom['relation'], 'INSUFFICIENT')
                    self.assertEqual(atom['citations'], [])
        service.retriever.retrieve_many.assert_not_called()
        service.run(claims(items), items, 'cand_scope', 'sag_atomic', fresh_atomic=True, local_only=True)
        self.assertEqual(model.complete_structured.call_count, 2)

    def test_mixed_materials_refresh_both_supported_and_unlinked_experiences(self):
        items = fixture()
        attach_proof([items[0], items[2]])
        model = Model()
        model.complete_structured = MagicMock(wraps=model.complete_structured)
        service = GroundingService(retriever=AllSources(), model=model)
        for _ in range(2):
            model.complete_structured.reset_mock()
            _, _, report = service.run(claims(items), items, 'cand_scope', 'sag_atomic', fresh_atomic=True)
            self.assertIsNone(report['error'])
            sourced_id = items[2]['claims'][0]['claim_id']
            self.assertTrue(report['results'][sourced_id]['retrieved_sources'])
            self.assertTrue(any(call.args[0].startswith('Check') and sourced_id in call.args[1]
                                for call in model.complete_structured.call_args_list))
            for item in (items[1], items[3]):
                cid = item['claims'][0]['claim_id']
                self.assertEqual(report['results'][cid]['atoms'][0]['method'], 'model_split_without_sources')
                self.assertEqual(report['results'][cid]['state'], 'NEEDS_REVIEW')

    def test_explicit_recheck_reports_provider_failure_without_sources(self):
        items = fixture()
        model = MagicMock()
        model.complete_structured.side_effect = ModelFailure('timeout', code='MODEL_TIMEOUT', retryable=False)
        _, checks, report = GroundingService(model=model).run(claims(items), items, 'cand_scope', 'sag_atomic', fresh_atomic=True)
        self.assertEqual(report['error_code'], 'MODEL_TIMEOUT')
        self.assertEqual(report['failure_stage'], '无材料陈述的事实拆分')
        self.assertTrue(all(not c['grounded'] for c in checks))

    def test_all_three_experience_kinds_require_originals(self):
        items = fixture()
        retriever = MagicMock()
        _, checks, report = GroundingService(retriever=retriever, model=MagicMock()).run(
            claims(items), items, 'cand_scope', 'sag_atomic')
        self.assertEqual([v['state'] for v in checks], ['VERIFIED', 'NEEDS_REVIEW', 'NEEDS_REVIEW', 'NEEDS_REVIEW'])
        retriever.retrieve_many.assert_not_called()
        self.assertTrue(all(report['results'][c['claim_id']]['verification_scope'] == 'experience'
                            for c in claims(items[1:])))

    def test_personal_text_excluded_from_retrieval_and_model_and_experiences_can_block(self):
        items = fixture()
        attach_proof(items)
        retriever = MagicMock(wraps=AllSources())
        class RecordingModel(Model):
            def __init__(self):
                super().__init__(fullbad=True)
                self.inputs = []

            def complete_structured(self, prompt, data, schema):
                self.inputs.append(data)
                return super().complete_structured(prompt, data, schema)

        model = RecordingModel()
        _, checks, report = GroundingService(retriever=retriever, model=model).run(
            claims(items), items, 'cand_scope', 'sag_atomic')
        self.assertEqual([v['state'] for v in checks], ['VERIFIED', 'NEEDS_REVIEW', 'NEEDS_REVIEW', 'NEEDS_REVIEW'])
        for call in retriever.retrieve_many.call_args_list:
            self.assertNotIn('Private School', json.dumps(call.args))
            self.assertEqual(len(call.args[0]), 3)
        self.assertIsNone(report['error'])
        self.assertTrue(model.inputs)
        for data in model.inputs:
            self.assertNotIn('Private School', data)

    def test_provider_failure_cannot_bypass_internship_checks(self):
        items = fixture()
        attach_proof(items)
        class TimedOutModel:
            def complete_structured(self, prompt, data, schema):
                raise ModelFailure('offline', code='MODEL_TIMEOUT', retryable=False)
        model = TimedOutModel()
        _, checks, report = GroundingService(retriever=AllSources(), model=model).run(
            claims(items), items, 'cand_scope', 'sag_atomic')
        self.assertEqual([v['state'] for v in checks], ['VERIFIED', 'NEEDS_REVIEW', 'NEEDS_REVIEW', 'NEEDS_REVIEW'])
        self.assertFalse(checks[0]['grounded'])
        self.assertEqual(report['error_code'], 'MODEL_TIMEOUT')
        self.assertEqual(report['failure_stage'], '原子事实核验')
        self.assertIn('超时', report['error'])

    def test_personal_id_cannot_be_reused_for_an_edited_experience_claim(self):
        items = fixture()[:1]
        changed = claims(items)
        changed[0]['text'] = 'Led deployment and improved performance 900%.'
        _, checks, _ = GroundingService(model=MagicMock()).run(changed, items, 'cand_scope', 'sag_atomic')
        self.assertEqual(checks[0]['state'], 'BLOCKED')

    def test_personal_only_export_does_not_require_model_credentials(self):
        form = {'candidateId': 'cand_scope', 'education': [
            {'id': 'edu', 'school': 'Private School', 'degree': 'BSc', 'major': 'Math'}]}
        request = {'candidate_id': 'cand_scope', 'jd_text': 'Engineer requires Python.',
                   'claims': claims(experiences_from_resume_draft(form)), 'resume_draft': form,
                   'human_confirmed': True}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'APPLYGUARD_LOCAL_DIR': directory, 'APPLYGUARD_EVIDENCE_DIR': directory,
                'APPLYGUARD_GROUNDING_MODE': 'sag_atomic', 'APPLYGUARD_AI_API_KEY': ''}):
            with patch('backend.services.grounded_workflow.HttpModelClient', side_effect=AssertionError('model forbidden')):
                result = export_grounded(Path(directory)/'unused.json', request)
        self.assertEqual(result['text'], request['claims'][0]['text'])

    def test_internship_export_requires_current_linked_original_even_with_personal_profile(self):
        form = {'candidateId': 'cand_scope', 'education': [
            {'id': 'edu', 'school': 'Private School', 'degree': 'BSc', 'major': 'Math'}],
            'internships': [{'id': 'intern', 'organization': 'Lab', 'description': 'Alex wrote Python tests.'}]}
        request = {'candidate_id': 'cand_scope', 'jd_text': 'Engineer requires Python testing.',
                   'claims': claims(experiences_from_resume_draft(form)), 'resume_draft': form,
                   'human_confirmed': True}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'APPLYGUARD_LOCAL_DIR': directory, 'APPLYGUARD_EVIDENCE_DIR': directory,
                'APPLYGUARD_GROUNDING_MODE': 'sag_atomic', 'APPLYGUARD_STRONG_AI_MODEL': ''}):
            ws = workspace.create_workspace('Fictional internship')
            source = workspace.import_files(ws['workspace_id'], [{'relative_path': 'intern.md',
                'content_base64': base64.b64encode(b'Alex wrote Python tests.').decode()}])['files'][0]
            workspace.review_evidence(source['evidence_id'], {'normalized_fields': {}, 'review_state': 'REVIEWED'})
            link = {'target_type': 'internship', 'target_id': 'intern', 'evidence_id': source['evidence_id']}
            workspace.create_link(link)
            service = GroundingService(retriever=AllSources(), model=Model())
            with patch('backend.services.grounded_workflow.GroundingService', return_value=service):
                self.assertIn('Alex wrote Python tests.', export_grounded(Path(directory)/'unused.json', request)['text'])
                workspace.create_link({**link, 'link_state': 'REJECTED'})
                with self.assertRaises(ValueError):
                    export_grounded(Path(directory)/'unused.json', request)


if __name__ == '__main__':
    unittest.main()
