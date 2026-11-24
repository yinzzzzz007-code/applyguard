import json,sqlite3,unittest
from unittest.mock import patch
from backend.services import job_recommendation as rec,job_alerts

class RecommendationTests(unittest.TestCase):
 def test_profile_uses_professional_fields_only(self):
  profile={'basic':{'idNo':'SECRET_ID','phone':'SECRET_PHONE'},'education':[{'major':'数据科学'}],
   'projects':[{'title':'RAG','description':'Python 检索服务'}],'extras':{'skills':'PyTorch'},'intention':{'expectRole':'算法研发'}}
  text=' '.join(rec.profile_texts(profile))
  self.assertIn('Python',text);self.assertIn('数据科学',text);self.assertNotIn('SECRET',text)
 def test_feedback_changes_related_interest_without_making_it_a_probability(self):
  jobs=[{'id':'a','title':'Agent','interest':1},{'id':'b','title':'RAG'},{'id':'c','title':'材料'}]
  with patch.object(rec,'vectorize',return_value=[[1.,0.],[1.,0.],[.9,.1],[0.,1.]]):
   scores=rec.semantic_scores(['LLM'],jobs)
  self.assertGreater(scores['b']['semantic'],scores['c']['semantic'])
  self.assertGreater(scores['b']['affinity'],scores['c']['affinity'])
 def test_company_and_duplicate_diversity_preserves_all_jobs(self):
  jobs=[{'id':'a','title':'AI','company':'A','recommendation_score':90},
        {'id':'b','title':'AI','company':'A','recommendation_score':89},
        {'id':'c','title':'Agent','company':'B','recommendation_score':86}]
  ranked=rec.rerank(jobs)
  self.assertEqual([j['id'] for j in ranked],['a','c','b'])
  self.assertEqual(set(j['id'] for j in ranked),{'a','b','c'})
 def test_feedback_is_reversible_and_rejects_invalid_values(self):
  conn=sqlite3.connect(':memory:');conn.row_factory=sqlite3.Row;self.addCleanup(conn.close)
  rec.save_feedback(conn,'job_one',-1);self.assertEqual(rec.feedback(conn)['job_one'],-1)
  rec.save_feedback(conn,'job_one',0);self.assertEqual(rec.feedback(conn)['job_one'],0)
  with self.assertRaises(ValueError):rec.save_feedback(conn,'job_one',True)
 def test_old_or_incomplete_jobs_stay_available_but_rank_lower(self):
  jobs=[{'id':'a','title':'AI','company':'A','status':'open','match_score':80},
        {'id':'b','title':'AI','company':'B','status':'closed','match_score':80}]
  rec.decorate(jobs,{}, {})
  self.assertGreater(jobs[0]['recommendation_score'],jobs[1]['recommendation_score'])
 def test_alert_pagination_has_no_hidden_200_message_ceiling(self):
  conn=sqlite3.connect(':memory:');conn.row_factory=sqlite3.Row;self.addCleanup(conn.close)
  conn.executescript('CREATE TABLE opportunities(id TEXT,payload TEXT); CREATE TABLE job_alerts(event_key TEXT,job_id TEXT,created_at TEXT,read_at TEXT);')
  conn.executemany('INSERT INTO job_alerts VALUES(?,?,?,NULL)',[(str(i),'job','2026-11-23') for i in range(325)])
  first=job_alerts.list_alerts(conn,'/alerts?unread=true&limit=200')
  second=job_alerts.list_alerts(conn,'/alerts?unread=true&limit=200&offset=200')
  self.assertEqual(first['total'],325);self.assertEqual(len(first['items'])+len(second['items']),325)
  self.assertEqual(len({r['event_key'] for r in first['items']+second['items']}),325)
  self.assertFalse(second['has_more'])
  with self.assertRaises(ValueError):job_alerts.list_alerts(conn,'/alerts?offset=-1')
