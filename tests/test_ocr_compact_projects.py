import unittest

from backend.services.resume_sections import education, heading_kind, project_entries


class CompactProjectHeadersTests(unittest.TestCase):
    def test_ocr_headers_next_to_technology_and_dates(self):
        lines = [
            'LangGraph,RAG,OpenAI,FAISS,Next.js',
            'Multi-AgentResearchAssistant', 'Feb2025-Apr2025',
            'Built a retrieval pipeline.',
            'AICopilotforSQLAnalytics', 'LangChain,PostgreSQL,Docker', 'Nov2024-Jan2025',
            'Built an analytics tool.',
            'DocumentIntelligenceRAGSystem', 'RAG,LangChain,AWS', 'Aug2024-Oct2024',
            'Deployed the system.',
        ]
        rows = project_entries(lines, 'projects')
        self.assertEqual([row['title'] for row in rows], [
            'Multi-AgentResearchAssistant', 'AICopilotforSQLAnalytics', 'DocumentIntelligenceRAGSystem'])
        self.assertIn('Built a retrieval pipeline.', rows[0]['description'])

    def test_compact_prose_without_date_is_not_new_project(self):
        rows = project_entries(['Research Project', 'DeployedonAWSwithRESTAPI', 'Further analysis.'], 'projects')
        self.assertEqual(len(rows), 1)

    def test_ocr_bullets_before_school_names(self):
        rows = education(['· Georgia Institute of Technology', 'Master of Science',
                          '. Birla Institute of Technology and Science', 'Bachelor of Engineering'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['school'], 'Georgia Institute of Technology')
        self.assertEqual(rows[1]['school'], 'Birla Institute of Technology and Science')

    def test_compact_ocr_experience_heading(self):
        self.assertEqual(heading_kind('PROFESSIONALEXPERIENCE'), 'internships')


if __name__ == '__main__':
    unittest.main()
