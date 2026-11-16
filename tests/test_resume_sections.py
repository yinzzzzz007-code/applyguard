"""Fictional bilingual fixtures; no user's CV or contact details are committed."""
import unittest
from unittest.mock import patch
from backend.services.resume_parser import extract_resume_from_text,parse_resume_pdf
from backend.services.resume_sections import dates

CV='''林晓舟   Lin Zhou
示例理工大学 · 计算学院 · 软件工程
Rank 3/80 · GPA 90/100 · CET-6 520
lin@example.test
教育背景 EDUCATION
示例理工大学 · 计算学院 2023 – 2027
软件工程本科；专业排名 3/80（Top 4%），GPA 90/100。
研究兴趣 RESEARCH INTERESTS
Human-AI Interaction / Agent Evaluation
重点科研经历 SELECTED RESEARCH
DialogStudy —— Evidence-Grounded Partner-
Sensitive Communication HCI 2027 Submitted · 独立一作
研究：比较行为差异，没有开展生产部署。
贡献：负责设计、评测和写作，已投稿。
SocialProbe —— Personality-Aware Social AI ABC 2026 Accepted · 共同第一作者
研究：比较多种人格条件。
贡献：共同第一作者；论文已录用。
Example Model Reasoning Challenge Kaggle Silver · 120/3000
研究：使用 LoRA 训练，部分方法没有继续使用。
贡献：负责数据构造和训练评测。
当前研究 CURRENT RESEARCH
SceneLab 3D World Generation & Evaluation
以场景生成为研究目标，分析物体布局。
CachePlan — Adaptive LLM Inference ABC 暑研
围绕推理速度开展测量，尚未上线。
工程项目 ENGINEERING PROJECTS
StudyGuard — 专注助手 项目负责人
负责设计和实现。
ProofVault — 求职助手 主要贡献者
保留人工确认，未进行自动投递。
DocBot — Secure RAG Assistant 项目负责人
使用检索与权限校验。
其他经历与荣誉 OTHER EXPERIENCE & HONORS
国家级大创 AgentTown 仿真（核心成员） · Multi-Agent PPO 调度（项目负责人） · MCM/ICM Honorable
Mention · ExampleCup 华南赛区二等奖
技术技能 TECHNICAL SKILLS
Python · PyTorch · RAG · Linux
'''

class ResumeSectionsTests(unittest.TestCase):
    def test_schools_after_degree_and_english_school_headings(self):
        cn = '教育经历\n信息技术硕士|示例大学\n2024.03 - 2026.10\n体育教育本科|另一个大学\n2018.09 - 2022.09\n技能\nPython'
        rows = extract_resume_from_text(cn)['education']
        self.assertEqual([r['school'] for r in rows], ['示例大学', '另一个大学'])
        self.assertEqual([(r['start'], r['end']) for r in rows], [('2024-03', '2026-10'), ('2018-09', '2022-09')])
        en = 'EDUCATION\nEXAMPLE BUSINESS SCHOOL\nMasters in Financial Analysis\n2023 – 2024\nUNIVERSITY OF EXAMPLE\nBA in Economics\n2020 – 2023\nEXPERIENCE\nFICTIONAL BANK\nAnalyst Intern\n• Analysed data.\nEXAMPLE FIRM\nSummer Analyst\n• Prepared research.\nSKILLS\nPython'
        form = extract_resume_from_text(en)
        self.assertEqual([r['school'] for r in form['education']], ['EXAMPLE BUSINESS SCHOOL', 'UNIVERSITY OF EXAMPLE'])
        self.assertEqual(len(form['internships']), 2)
        self.assertNotIn('Analyst Intern', form['education'][-1]['school'])

    def test_ocr_english_experience_keeps_employer_role_dates_and_sentences_together(self):
        from backend.services.resume_sections import project_entries
        lines = ['EXAMPLE BANK', 'London, UK', 'Research Analyst Intern, Fixed Income', 'Jan 2024 - Apr 2024',
                 'Cleaned daily pricing records using Python.', 'Supported M&A analysis for three targets.',
                 'SAMPLE FIRM', 'London, UK', 'Investment Banking Summer Analyst', 'Jun 2023 – Aug 2023',
                 'Supported M&A due diligence for three targets.', 'Prepared research reports.']
        rows = project_entries(lines, 'internships')
        self.assertEqual([r['title'] for r in rows], ['EXAMPLE BANK', 'SAMPLE FIRM'])
        self.assertIn('Research Analyst Intern', rows[0]['description'])
        self.assertIn('Supported M&A', rows[1]['description'])
        self.assertEqual((rows[0]['start'], rows[0]['end']), ('2024-01', '2024-04'))

    def test_english_date_only_ocr_lines_belong_to_previous_project(self):
        from backend.services.resume_sections import project_entries
        lines = ['Research Assistant', 'Feb 2025 - Apr 2025', 'Built a research tool.',
                 'Analytics Copilot', 'Nov 2024 - Jan 2025', 'Built an analytics tool.']
        rows = project_entries(lines, 'projects')
        self.assertEqual([r['title'] for r in rows], ['Research Assistant', 'Analytics Copilot'])
        self.assertEqual([(r['start'], r['end']) for r in rows], [('2025-02', '2025-04'), ('2024-11', '2025-01')])
        self.assertEqual(dates('Dec 2025 - Jan 2025'), ('', ''))

    def test_chinese_project_role_after_comma_starts_new_entry(self):
        text = ('项目经历\nClinicLab AI，独立开发| GitHub\n项目简介：完成检索原型。\n'
                '多模态翻译 Agent，核心开发成员\n项目简介：完成协作翻译。\n专业技能\nPython')
        rows = extract_resume_from_text(text)['projects']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['role'], '核心开发成员')

    def test_ocr_experience_with_volunteer_header_stays_separate(self):
        text = ('实习经历\nAI开发实习生|示例咨询公司\n2025.12-2026.04\n负责开发原型。\n'
                'IT 技术支持志愿者 | 示例市政府\n2025.10 - 至今\n为社区提供技术支持。\n技能\nPython')
        rows = extract_resume_from_text(text)['internships']
        self.assertEqual(len(rows), 2)
        self.assertIn('志愿者', rows[1]['title'])
        self.assertEqual([(r['start'],r['end']) for r in rows], [('2025-12','2026-04'),('2025-10','至今')])

    def test_research_and_awards_with_right_aligned_dates(self):
        text = """科研与项目经历
2026
Atlas：离线测试工具 2026.03 – 至今
软件组——测试方案设计｜示例实验室
• 整理异常输入和错误恢复流程。
Notes: A Study of Personal Notes Through Visual Editing 2026.04 – 2026.06
共 同第一作者
• 分析笔记中的编辑操作。
竞赛获奖
示例数学竞赛 Meritorious Winner（M奖）｜队长 2026
示例应用挑战赛二等奖 2025
专业技能
Python
"""
        form = extract_resume_from_text(text)
        self.assertEqual([row['title'] for row in form['projects']], [
            'Atlas：离线测试工具', 'Notes: A Study of Personal Notes Through Visual Editing',
        ])
        self.assertEqual([row['role'] for row in form['projects']], ['软件组', '共同第一作者'])
        self.assertEqual(form['projects'][0]['organization'], '示例实验室')
        self.assertEqual([(row['start'], row['end']) for row in form['projects']], [
            ('2026-03', '至今'), ('2026-04', '2026-06'),
        ])
        self.assertEqual([(row['name'], row['date']) for row in form['awards']], [
            ('示例数学竞赛 Meritorious Winner（M奖）', '2026'), ('示例应用挑战赛二等奖', '2025'),
        ])
        self.assertNotIn('竞赛获奖', form['projects'][1]['description'])
        self.assertIn('队长', form['awards'][0]['description'])

    def test_unlabelled_bilingual_header_and_missing_identity_fields(self):
        form=extract_resume_from_text(CV)
        self.assertEqual(form['basic']['name'],'林晓舟')
        self.assertEqual(form['basic']['email'],'lin@example.test')
        for field in ['phone','gender','city','birthday']:self.assertEqual(form['basic'][field],'')
    def test_education_does_not_confuse_rank_with_major_or_invent_month(self):
        edu=extract_resume_from_text(CV)['education'][0]
        self.assertEqual((edu['school'],edu['major'],edu['degree']),('示例理工大学','软件工程','本科'))
        self.assertEqual((edu['start'],edu['end']),('2023','2027'))
        self.assertEqual(edu['rank'],'3/80（Top 4%）')
    def test_multiline_title_and_distinct_research_engineering_projects(self):
        rows=extract_resume_from_text(CV)['projects'];self.assertEqual(len(rows),10)
        self.assertEqual(rows[0]['title'],'DialogStudy —— Evidence-Grounded Partner-Sensitive Communication')
        self.assertEqual(rows[1]['title'],'SocialProbe —— Personality-Aware Social AI')
        self.assertEqual(rows[0]['role'],'独立一作')
        self.assertIn('Submitted',rows[0]['description']);self.assertNotIn('Accepted',rows[0]['description'])
        self.assertIn('没有开展生产部署',rows[0]['description'])
        self.assertTrue(any(r['title'].startswith('CachePlan') for r in rows))
        self.assertFalse(any('TECHNICAL SKILLS' in r['description'] for r in rows))
    def test_mixed_honors_are_not_headings_or_experience_paragraphs(self):
        form=extract_resume_from_text(CV);names=[r['name'] for r in form['awards']]
        self.assertEqual(len(names),3)
        self.assertIn('MCM/ICM Honorable Mention',names)
        self.assertFalse(any('EXPERIENCE' in n or 'Python' in n or 'AgentTown' in n for n in names))
        self.assertEqual(form['extras']['skills'],'Python · PyTorch · RAG · Linux')
        self.assertEqual(form['internships'],[])
        self.assertIn('GPA 90/100',form['extras']['summary'])
        self.assertIn('CET-6 520',form['extras']['summary'])
    def test_heading_words_in_description_do_not_cut_sections(self):
        form=extract_resume_from_text('项目经历\nProofVault — 申请助手\n负责项目经历匹配与专业技能分析，保留全部记录。\n技术技能\nPython')
        self.assertEqual(len(form['projects']),1)
        self.assertIn('负责项目经历匹配与专业技能分析',form['projects'][0]['description'])
    def test_header_labels_are_not_mistaken_for_names(self):
        for text in ['个人简历\n教育背景\n示例理工大学','教育背景\n软件工程本科','技术技能\nPython']:
            self.assertEqual(extract_resume_from_text(text)['basic']['name'],'')
        self.assertEqual(extract_resume_from_text('简历\n姓名：赵小雨\n手机：13800000001')['basic']['name'],'赵小雨')

    def test_pdf_header_with_reordered_labels_and_grouped_phone(self):
        text = (
            '邮箱： 电话： 赵小雨\n'
            '138-0000-0001 fictional@example.test\n'
            '教育背景\n'
            '2024.09–2028.06 示例理工大学（STU）\n'
            '数据科学与大数据技术专业（本科） 广州\n'
            '科研与项目经历\n'
            '亚太地区大学生示例数学建模竞赛三等奖\n'
            '专业技能\nPython'
        )
        form = extract_resume_from_text(text)
        self.assertEqual(form['basic']['name'], '赵小雨')
        self.assertEqual(form['basic']['phone'], '13800000001')
        self.assertEqual(form['basic']['email'], 'fictional@example.test')
        self.assertEqual(len(form['education']), 1)
        self.assertEqual(form['education'][0]['major'], '数据科学与大数据技术')

    def test_contact_labels_and_numeric_email_are_not_contact_values(self):
        text = '联系方式\n邮箱： 电话：\n13800000001@example.test'
        basic = extract_resume_from_text(text)['basic']
        self.assertEqual(basic['name'], '')
        self.assertEqual(basic['phone'], '')

    def test_phone_with_spaces_and_country_code(self):
        basic = extract_resume_from_text('手机：+86 138 0000 0001')['basic']
        self.assertEqual(basic['phone'], '13800000001')
    def test_month_precision_and_multiple_education_records(self):
        self.assertEqual(dates('2024.09 - 2026.06'),('2024-09','2026-06'))
        text='教育经历\n示例理工大学 2020–2024\n软件工程本科\n示例科技大学 2024.09 - 2026.06\n专业：计算机科学\n硕士\n技能\nPython'
        self.assertEqual(len(extract_resume_from_text(text)['education']),2)
    def test_offline_pdf_pipeline_keeps_all_rows_without_model(self):
        # Exercises the same PDF endpoint adapter; PDF decoding is isolated in this fixture.
        with patch('backend.services.resume_parser.pdf_bytes_to_text',return_value=CV),patch('backend.services.resume_parser.HttpModelClient',side_effect=AssertionError('offline only')):
            response=parse_resume_pdf('JVBERi0xLjQ=','fictional.pdf')
        self.assertEqual(len(response['form']['projects']),10)
        self.assertEqual(response['extractor'],'规则抽取')

class EnglishSentenceBoundaryTests(unittest.TestCase):
    def test_capitalized_technical_sentence_is_not_a_new_project(self):
        from backend.services.resume_sections import project_entries
        entries = project_entries(['Atlas API - 2025.01 - 2025.06',
            'Built Python HTTP API tests in an offline prototype.',
            'Reduced latency by approximately 30 percent in offline tests only.',
            'No production deployment.'], 'projects')
        self.assertEqual(len(entries), 1)
        self.assertIn('No production deployment.', entries[0]['description'])

if __name__=='__main__':unittest.main()
