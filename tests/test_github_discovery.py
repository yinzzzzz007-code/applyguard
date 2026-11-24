import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from backend.services.github_discovery import discover, pin
from backend.services import agent_bridge

def row(name='sample-user/project',private=False):
    return {'full_name':name,'private':private,'default_branch':'main','description':'Project'}

class GithubDiscoveryTests(unittest.TestCase):
    def test_natural_username_public_only(self):
        before=set(agent_bridge.GRANTS)
        fetch=Mock(return_value=[row(),row('sample-user/private',True)])
        result=discover({'query':'sample-user的公开仓库'},fetch)
        self.assertEqual([r['repo'] for r in result['items']],['sample-user/project'])
        self.assertTrue(fetch.call_args.args[0].startswith('users/sample-user/repos?'))
        self.assertIs(fetch.call_args.args[1],False)
        self.assertEqual(set(agent_bridge.GRANTS),before)
    def test_email_requires_account_selection(self):
        fetch=Mock(return_value={'items':[{'login':'one'},{'login':'two'}],'total_count':2})
        result=discover({'query':'person@example.com'},fetch)
        self.assertEqual(len(result['accounts']),2)
        self.assertEqual(result['items'],[])
        self.assertEqual(fetch.call_count,1)
        self.assertIn('in%3Aemail',fetch.call_args.args[0])
    def test_email_not_public_is_explained(self):
        result=discover({'query':'person@example.com'},Mock(return_value={'items':[],'total_count':0}))
        self.assertIn('不代表',result['notice'])
    def test_keywords_and_paging_are_public(self):
        fetch=Mock(return_value={'items':[row()],'total_count':100,'incomplete_results':True})
        result=discover({'query':'RAG agent','kind':'keyword','page':2},fetch)
        self.assertTrue(result['has_more'])
        self.assertIn('is%3Apublic',fetch.call_args.args[0])
        self.assertIn('部分',result['notice'])
        for query in ('github_pat_secret','RAG is:private'):
            with self.assertRaises(ValueError):discover({'query':query,'kind':'keyword'},fetch)
    def test_pin_checks_visibility_and_freezes_commit(self):
        fetch=Mock(side_effect=[row(),{'object':{'type':'commit','sha':'a'*40}}])
        self.assertEqual(pin({'repo':'sample-user/project'},fetch)['spec'],'sample-user/project@'+'a'*40)
        self.assertTrue(all(call.args[1] is False for call in fetch.call_args_list))
        with self.assertRaises(ValueError):pin({'repo':'sample-user/project'},Mock(return_value=row(private=True)))
    def test_forbidden_is_not_reported_as_rate_limit(self):
        fetch=Mock(side_effect=HTTPError('url',403,'blocked',{},None))
        with self.assertRaisesRegex(ValueError,'HTTP 403'):discover({'query':'octocat'},fetch)

    def test_primary_limit_switches_only_to_public_owner_search(self):
        limit=HTTPError('url',403,'blocked',{'X-RateLimit-Remaining':'0','X-RateLimit-Reset':'1970000000'},None)
        results={'items':[row('octocat/code'),row('other/unrelated'),row('octocat/secret',True)],'total_count':40}
        fetch=Mock(side_effect=[limit,results,results])
        first=discover({'query':'octocat'},fetch)
        self.assertEqual([x['repo'] for x in first['items']],['octocat/code'])
        self.assertEqual(first['listing'],'owner_search')
        discover({'query':'octocat','page':2,'listing':first['listing']},fetch)
        self.assertTrue(all(call.args[1] is False for call in fetch.call_args_list))
        self.assertIn('user%3Aoctocat',fetch.call_args_list[-1].args[0])

    def test_secondary_limit_shows_retry_time_and_suppresses_repeated_requests(self):
        fetch=Mock(side_effect=HTTPError('url',429,'busy',{'Retry-After':'90'},None))
        for query in ('octocat','another'):
            with self.assertRaisesRegex(ValueError,'北京时间'):discover({'query':query},fetch)
        self.assertEqual(fetch.call_count,1)
    def test_ui_dispatch_uses_same_public_boundary(self):
        with patch.object(agent_bridge,'gh',return_value=[row()]):
            self.assertEqual(len(agent_bridge.ui_call({'action':'github_discover','query':'sample-user'})['items']),1)

    def test_public_refs_fallback_does_not_inherit_credentials(self):
        import subprocess
        from backend.services.github_discovery import public_git_head
        completed=subprocess.CompletedProcess([],0,'ref: refs/heads/main\tHEAD\n'+'b'*40+'\tHEAD\n','')
        with patch.dict('os.environ',{'APPLYGUARD_GITHUB_TOKEN':'secret','GH_TOKEN':'secret'}),patch('subprocess.run',return_value=completed) as run:
            result=public_git_head('sample-user/project')
            self.assertEqual(result['sha'],'b'*40)
            self.assertNotIn('GH_TOKEN',run.call_args.kwargs['env'])
            self.assertNotIn('APPLYGUARD_GITHUB_TOKEN',run.call_args.kwargs['env'])
            self.assertIn('credential.helper=',run.call_args.args[0])
