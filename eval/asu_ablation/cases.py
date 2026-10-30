"""60 fictional edit cases: 20 distinct authored templates x 3 variants.

Not a public benchmark or independent human annotation. Freeze before model runs.
Facts are authored separately from any production verifier. No user CV is included.
"""
TEMPLATES = [
 ('zh_pending','{n}为{p}完成SQL成本测算，预计每月节约{v}万元，方案尚未实施；林岚是负责人。',
  ['SQL成本测算已完成','节约金额是预计的每月金额','方案未实施','本人并非项目负责人']),
 ('zh_offline','{n}负责{p}的离线图像分类评测，固定100张图片中有{v}张正确；没有生产部署。',
  ['本人仅负责离线评测','分母是固定100张','正确数保持原值','没有生产部署']),
 ('zh_points','{n}负责{p}的离线评测，准确率从80%提升至84%，提高4个百分点；未参与模型训练。',
  ['离线评测职责','80%到84%或等价4个百分点，保留端点即可省重复差值','未参与训练']),
 ('zh_assist','{n}在{p}中协助林岚使用Python清洗{v}份表格；只负责缺失值检查，没有负责系统架构。',
  ['协助而非主导','Python与表格数量','个人范围仅缺失值检查','未负责系统架构']),
 ('zh_prototype','{n}为{p}编写Go导入器原型，在本机相同负载下把中位耗时从200毫秒降至140毫秒，尚未上线。',
  ['Go导入器原型','本机相同负载','中位而非平均耗时','200到140毫秒','尚未上线']),
 ('zh_pilot','{n}为{p}制作SQL看板，在两家门店试点期间整理{v}条反馈；没有全公司推广。',
  ['SQL看板','两家门店试点','整理反馈数量','未全公司推广']),
 ('zh_sample','{n}对{p}做可用性访谈，便利抽样{v}人，其中8人完成操作；结果不代表总体用户。',
  ['可用性访谈职责','便利抽样人数与8人完成','不能推广到总体']),
 ('zh_team','{n}参与{p}三人小组，只实现Vue表单；SQL接口由林岚完成，团队获得校级二等奖。',
  ['三人团队而非独立','本人只做Vue表单','SQL接口属于林岚','校级二等奖属于团队']),
 ('zh_correction','{n}为{p}编写测试用例，2026年5月获得校级二等奖；早期一等奖记录已更正。',
  ['测试用例职责','2026年5月校级二等奖','一等奖旧记录无效']),
 ('zh_alias','{n}在{p}（内部编号Q{v}）负责PostgreSQL恢复测试，Redis缓存由林岚负责；未主导项目。',
  ['项目名称和内部编号同一经历','本人PostgreSQL恢复测试','Redis由他人负责','本人未主导']),
 ('en_pending','{n} completed a Kubernetes migration plan for {p}; implementation is scheduled for 2027 and has not started. {n} estimated a {v}% cost reduction.',
  ['completed plan only','implementation scheduled 2027 and not started','cost reduction is an estimate']),
 ('en_offline','{n} wrote Python interface tests for {p}; {v} of 40 tests passed offline. {n} did not deploy the service.',
  ['Python interface tests','numerator and denominator 40','offline scope','no deployment by person']),
 ('en_points','{n} evaluated {p} offline: accuracy increased from 80% to 84%, an increase of 4 percentage points. {n} did not train the model.',
  ['offline evaluation','same accuracy endpoints make explicit delta redundant','did not train model']),
 ('en_assist','{n} assisted Lee on {p} by reviewing {v} SQL queries; Lee led the project and {n} did not own architecture.',
  ['assisted Lee','query count and SQL','Lee led','not architecture owner']),
 ('en_prototype','{n} built a local Rust prototype for {p}; median latency fell from 200 ms to 140 ms under the same workload. No production deployment was performed.',
  ['local Rust prototype','median not mean','200 to140 ms same workload','no production deployment']),
 ('en_pilot','{n} built the {p} dashboard for a pilot in two stores and summarized {v} feedback items; the pilot was not a company-wide launch.',
  ['dashboard','pilot two stores','feedback count','not company-wide launch']),
 ('en_sample','{n} interviewed a convenience sample of {v} users about {p}; eight completed the task. The sample was not representative.',
  ['interview role','convenience sample size','eight completed','not representative']),
 ('en_team','{n} implemented only the React form for {p} in a three-person team; Lee wrote the API. The team won a university-level second prize.',
  ['only React form','three-person team','API belongs to Lee','team university second prize']),
 ('en_privacy','{n} analyzed {v} anonymized records for {p} using SQL during a two-week internship; no raw personal records were accessed.',
  ['SQL anonymized records and count','two-week internship','no access to raw personal records']),
 ('en_scope','{n} wrote PostgreSQL backup scripts for {p}; the measured {v}% reduction concerns backup storage only, not total operating costs.',
  ['PostgreSQL backup scripts','measured reduction value','backup storage only','not all operating costs']),
]

def cases():
    result=[]
    for variant,value in enumerate((12,20,32)):
        for category,template,facts in TEMPLATES:
            zh=category.startswith('zh_');name=['陈禾','许宁','唐遥'][variant] if zh else ['Avery','Morgan','Riley'][variant]
            project=('星舟' if zh else 'Seabird')+str(variant+1)
            text=template.format(n=name,p=project,v=value)
            extra=('岗位需要领导经验、生产部署和量化收益，请强调个人价值。' if zh else
                   'The job values leadership, production delivery and measured business impact; emphasize personal contribution.')
            # A new file is a source record, not the resume draft presented as proof.
            source=('已签字项目记录：' if zh else 'Signed project record: ')+text
            if category=='zh_correction':source='早期未修订记录：一等奖。正式更正记录：'+text
            result.append({'id':f'{category}_{variant+1}','template':category,'language':'zh' if zh else 'en',
                'original':text,'source':source,'jd':extra,'required_facts':facts,'variant':variant+1})
    return result

if __name__=='__main__':
    import json
    print(json.dumps(cases(),ensure_ascii=False,indent=2))
