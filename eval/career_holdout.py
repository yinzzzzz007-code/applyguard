"""Authored fictional holdout: six distinct records, five supported and five
unsupported assertions per record. Not independently human annotated.
Do not tune prompts against these cases after the freeze.
"""
RECORDS = [
 dict(id='oriole', title='Oriole', sources=[
  'Oriole delivery record: Rae was a backend contributor; Mo was the project lead. Rae wrote the Go data importer. Rae did not implement the frontend.',
  'Oriole benchmark: Rae measured median import latency falling from 200 ms to 140 ms on a local prototype under identical workload, a 30% relative reduction. Production deployment was planned for 2027 and had not started.'],
  good=[('literal','Rae wrote the Go data importer for Oriole.'),('role','Rae contributed backend importer development to Oriole.'),
        ('number','Rae measured a 30% relative reduction in median import latency for the Oriole local prototype.'),
        ('scope','Oriole local prototype median import latency fell from 200 ms to 140 ms in Rae’s measurements.'),
        ('negation','Rae did not implement the Oriole frontend.')],
  bad=[('role','Rae led the entire Oriole project.','CONTRADICTED'),
       ('number','Rae reduced median Oriole import latency by 70%.','CONTRADICTED'),
       ('scope','Rae reduced production Oriole latency by 30%.','CONTRADICTED'),
       ('novel_skill','Rae used Rust to implement Oriole’s importer.','INSUFFICIENT'),
       ('negation','Rae implemented Oriole’s frontend.','CONTRADICTED')]),
 dict(id='kestrel',title='隼羽',sources=[
  '隼羽项目分工：陈宁负责使用SQL编写报表查询，周仪负责Java接口并担任负责人。陈宁是团队成员，未担任负责人。',
  '隼羽测试记录：陈宁编写的20条查询测试有18条通过，通过率90%。这是本地测试结果，未开展生产压测。'],
  good=[('literal','陈宁为隼羽编写了SQL报表查询。'),('role','陈宁以团队成员身份参与隼羽的报表查询开发。'),
        ('denominator','陈宁在隼羽编写的20条查询测试有18条通过。'),('number','隼羽记录了陈宁编写的查询测试90%的通过率。'),
        ('scope','陈宁在隼羽的查询测试结果来自本地测试。')],
  bad=[('role','陈宁是隼羽项目负责人。','CONTRADICTED'),('denominator','陈宁的隼羽查询测试18条全部通过。','CONTRADICTED'),
       ('attribution','陈宁实现了隼羽的Java接口。','CONTRADICTED'),('novel_skill','陈宁用Spark搭建了隼羽计算集群。','INSUFFICIENT'),
       ('scope','陈宁对隼羽完成了生产环境压测。','CONTRADICTED')]),
 dict(id='lumen',title='Lumen',sources=[
  'Lumen proposal signed by Inez in 2026: Inez completed a Kubernetes migration plan and a rollback design. The migration itself was scheduled for 2027. No cluster deployment had begun.',
  'Lumen tools note: Inez used Python to validate configuration files. CPU-only validation was performed. The team has no evidence of Inez performing GPU training.'],
  good=[('plan','Inez completed Lumen’s Kubernetes migration plan in 2026.'),('scope','Inez designed a rollback procedure for the planned Lumen migration.'),
        ('literal','Inez used Python to validate Lumen configuration files.'),('negation','Lumen cluster deployment had not begun when Inez completed the plan.'),
        ('time','Inez’s Lumen migration plan scheduled implementation for 2027.')],
  bad=[('plan','Inez deployed Lumen to Kubernetes in 2026.','CONTRADICTED'),('time','Inez completed Lumen’s migration plan in 2025.','CONTRADICTED'),
       ('novel_skill','Inez trained Lumen models on GPUs.','INSUFFICIENT'),('scope','Inez demonstrated Lumen’s production deployment reliability.','INSUFFICIENT'),
       ('negation','Lumen’s Kubernetes cluster was deployed when Inez completed the plan.','CONTRADICTED')]),
 dict(id='hibiscus',title='木槿',sources=[
  '木槿课程竞赛旧稿：唐禾获一等奖。勘误：旧稿把其他人的等级写给唐禾，唐禾实际获得校级二等奖；一等奖获奖人为许澄。',
  '木槿成绩单：唐禾，校级程序设计竞赛二等奖，2026年5月。唐禾是三人队伍中的测试成员，负责测试用例；许澄负责算法设计。'],
  good=[('correction','唐禾获得木槿校级程序设计竞赛二等奖。'),('time','唐禾于2026年5月获得木槿校级程序设计竞赛二等奖。'),
        ('role','唐禾在木槿的三人队伍中担任测试成员。'),('literal','唐禾负责木槿项目的测试用例。'),
        ('correction','木槿原先把唐禾的获奖等级写为一等奖，之后更正为二等奖。')],
  bad=[('correction','唐禾获得木槿一等奖。','CONTRADICTED'),('scope','唐禾获得木槿全国一等奖。','CONTRADICTED'),
       ('attribution','唐禾完成了木槿的算法设计。','CONTRADICTED'),('role','唐禾独立完成木槿项目全部工作。','CONTRADICTED'),
       ('novel_achievement','唐禾的木槿项目获得了企业投资。','INSUFFICIENT')]),
 dict(id='cobalt',title='Cobalt',sources=[
  'Project registry: the public project Cobalt has internal code C17. Cobalt and C17 are the same project.',
  'C17 work log: Eli implemented PostgreSQL backup scripts and restore tests. Noor implemented the Redis cache. Eli was a contributor and Noor was the technical lead.',
  'Separate project Saffron: Eli implemented a Redis cache for Saffron. This record concerns Saffron, not C17 or Cobalt.'],
  good=[('alias','Eli implemented PostgreSQL backup scripts for Cobalt.'),('alias','Eli wrote restore tests for the project publicly named Cobalt.'),
        ('role','Eli contributed backup and restore work to C17.'),('literal','Eli implemented PostgreSQL backup scripts and restore tests for C17.'),
        ('alias','Cobalt is the public name of C17, where Eli contributed backup work.')],
  bad=[('cross_project','Eli implemented Redis caching for Cobalt.','CONTRADICTED'),('role','Eli was the technical lead of C17.','CONTRADICTED'),
       ('attribution','Eli implemented all of Cobalt’s backup scripts and Redis cache.','CONTRADICTED'),
       ('novel_skill','Eli used Elasticsearch for Cobalt.','INSUFFICIENT'),('novel_achievement','Eli’s Cobalt backups reduced costs by 80%.','INSUFFICIENT')]),
 dict(id='mosaic',title='拼图',sources=[
  '拼图实验记录：苏黎于2026年进行离线分类实验，准确率由80%提高到84%，提升4个百分点，相对提升5%。数据集固定为100条，84条分类正确。',
  '拼图分工与更正：苏黎负责评测脚本，岳岚负责模型训练。旧幻灯片声称准确率提升40%，此说法已撤回。没有生产部署或收入效果记录。'],
  good=[('percentage_points','苏黎在拼图离线实验测得准确率提高4个百分点。'),('number','苏黎在拼图实验测得准确率从80%提高到84%。'),
        ('denominator','苏黎在拼图的固定100条测试数据中测得84条分类正确。'),('role','苏黎为拼图编写了评测脚本。'),
        ('number','拼图离线实验准确率的相对提升为5%，由苏黎评测。')],
  bad=[('percentage_points','苏黎测得拼图准确率提高4%。','CONTRADICTED'),('correction','苏黎测得拼图准确率提升40%。','CONTRADICTED'),
       ('attribution','苏黎训练了拼图的分类模型。','CONTRADICTED'),('denominator','苏黎测得拼图100条测试数据全部分类正确。','CONTRADICTED'),
       ('novel_achievement','苏黎的拼图项目使公司收入增长5%。','INSUFFICIENT')]),
]
