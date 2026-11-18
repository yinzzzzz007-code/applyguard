import json
import unittest
from unittest.mock import MagicMock, patch

from backend.services.interview_guide import generate_interview
from backend.services.model_client import ModelFailure
from backend.services.sag_grounding import GroundingUnavailable
from tests.test_api import ApiTests


def request():
    return {
        'jd_text': '后端开发实习，使用 Python 进行 API 服务开发、自动化测试和故障排查。',
        'resume': {
            'name': '虚构同学', 'email': 'private@example.test', 'idNo': 'private-id',
            'projects': [{'title': 'Atlas', 'description': '使用 Python 编写了接口测试。'}],
        },
    }


def response(projects=1):
    question = {'category': '项目', 'question': '如何测试接口？', 'answer': '我会先确认输入输出。',
                'basis': 'Atlas 项目与岗位测试要求', 'to_confirm': ['补充异常用例。']}
    keys = [f'project_{index + 1}' for index in range(projects)]
    keys += [f'general_{index + 1}' for index in range(max(0, 8 - projects))]
    return {
        'one_minute': '您好，我是虚构同学。' * 20,
        'three_minutes': '您好，我在 Atlas 项目中使用 Python 编写了接口测试。' * 20,
        'questions': {key: dict(question) for key in keys},
    }


class InterviewTests(unittest.TestCase):
    def test_uses_selected_projects_and_validates_output_without_contact_fields(self):
        model = MagicMock()
        model.complete_structured.return_value = response()
        with patch('backend.services.interview_guide.HttpModelClient', return_value=model):
            result = generate_interview(request())
        self.assertEqual(result['coverage_version'], 2)
        self.assertEqual(result['questions'][0]['project_name'], 'Atlas')
        self.assertEqual(len(result['questions']), 8)
        sent = json.loads(model.complete_structured.call_args.args[1])
        self.assertEqual(sent['resume']['projects'][0]['title'], 'Atlas')
        self.assertNotIn('email', sent['resume'])
        self.assertNotIn('idNo', sent['resume'])
        self.assertEqual(sent['target_job'], request()['jd_text'])

    def test_more_than_eight_projects_each_get_a_distinct_question_slot(self):
        body = request()
        body['resume']['projects'] = [{'title': f'项目 {index}', 'description': '虚构项目。'} for index in range(9)]
        model = MagicMock()
        model.complete_structured.return_value = response(projects=9)
        with patch('backend.services.interview_guide.HttpModelClient', return_value=model):
            result = generate_interview(body)
        self.assertEqual([row['project_index'] for row in result['questions']], list(range(1, 10)))
        self.assertEqual([row['project_name'] for row in result['questions']],
                         [row['title'] for row in body['resume']['projects']])

    def test_omitted_project_question_cannot_return_a_partial_guide(self):
        body = request()
        body['resume']['projects'].append({'title': 'Beacon'})
        model = MagicMock()
        model.complete_structured.return_value = response()
        with patch('backend.services.interview_guide.HttpModelClient', return_value=model):
            with self.assertRaises(GroundingUnavailable):
                generate_interview(body)

    def test_missing_experiences_do_not_call_model(self):
        body = request()
        body['resume']['projects'] = []
        with patch('backend.services.interview_guide.HttpModelClient') as constructor, self.assertRaises(ValueError):
            generate_interview(body)
        constructor.assert_not_called()

    def test_provider_failure_preserves_a_clear_retry_message(self):
        with patch('backend.services.interview_guide.HttpModelClient', side_effect=ModelFailure('fixture')):
            with self.assertRaisesRegex(GroundingUnavailable, '面经生成未完成'):
                generate_interview(request())


class InterviewHTTPTests(ApiTests):
    def test_interview_endpoint_success_and_input_error(self):
        model = MagicMock()
        model.complete_structured.return_value = response()
        with patch('backend.services.interview_guide.HttpModelClient', return_value=model):
            status, body = self.request('POST', '/api/v1/interview/generate', request())
        self.assertEqual(status, 200)
        self.assertEqual(len(body['questions']), 8)
        status, _ = self.request('POST', '/api/v1/interview/generate', {'jd_text': '太短'})
        self.assertEqual(status, 422)
