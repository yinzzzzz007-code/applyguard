"""Package source and synthetic validation outputs, never keys/runtime evidence."""
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'

def main():
    live=json.loads((OUT/'integration-live.json').read_text(encoding='utf-8'))
    if 'polish_atomic' not in live['runs']:raise SystemExit('Polishing recheck is not finished.')
    metrics=live['metrics']
    rows=[]
    for index,case in enumerate(live['cases']):
        states=[live['runs'][name]['response']['claim_verification'][index]['state']
            for name in ['good','bad','polish_atomic']]
        rows.append('| '+case['id']+' | '+' | '.join(states)+' |')
    times='\n'.join(f"- {name}：{run['elapsed_seconds']} 秒（整个5句请求）" for name,run in live['runs'].items())
    report=f'''# 实测记录：SAG 与原子事实核验

日期：2026-10-29。上游 ApplyGuard：43416faf6b575b9f4d1afc9ae834e87e89a2cb61（2026-10-22 20:15:03，北京时间）。
实际模型：ChatAnywhere 的 gpt-4o-mini；引擎：zleap-sag 0.15.0 full_expand，两跳，支持／反驳／更正三路查询。

本次真实 HTTP 端到端试验使用6份虚构原件、5组正反陈述，共10条固定输入，并另检验5条润色输出。是作者设计并标注的小样本，不是独立标注或统计代表性数据。

| 项目 | 有依据原句 | 问题原句 | SAG润色后再原子核验 |
| --- | --- | --- | --- |
{chr(10).join(rows)}

固定输入结果：漏放 {metrics['unsupported_accepted']}/{metrics['unsupported_total']}；严格误拦 {metrics['supported_blocked']}/{metrics['supported_total']}；复核 {metrics['review_total']}/{metrics['total']}；有依据陈述自动通过 {metrics['supported_accepted']}/{metrics['supported_total']}。
正确陈述未自动通过率为 2/5；因此“零误拦”不能理解成正例都通过。全部检索／模型流程未报告运行错误，但有原子覆盖或格式不完整的复核情况。

## 一个具体失败

SAG润色输出保留了“Alex led the Beacon project and implemented its React frontend.”；原件却写“Priya led the project and implemented React.”，Alex负责Redis。
输出附带的检索原文也包含这条分工和项目别名材料。这证明检索辅助润色仍可能保留职责错配。最后一列记录后置原子核验的实际处理结果，不能把SAG预览的全部NEEDS_REVIEW当成检测效果。

## 延迟与质量限制

{times}

good 包含首次建索引，其余复用同一来源快照索引；不是单句延迟、p95或受控性能对比。首次抽取有一次结构校验重试，最终建立索引。整个流程仍偏慢，下一步应加限定并发、相同快照检索缓存和清晰进度。不得为提速删掉反驳、更正材料。

拆分和判定使用同一模型，不能视为独立裁判。有依据的Forge句出现覆盖检查未通过，Cedar句出现原子结果结构不完整，均保留复核。这个试验没有相同生成提示下的向量RAG消融，不证明SAG本身优于普通RAG；更不证明零幻觉。5个负例零漏放的单侧95%漏放率上界仍约45%。

## 软件验证

- Python 回归：155项，154通过；1项因没有paddleocr而跳过（可选图片OCR，非SAG测试）。16项新增机制及HTTP集成测试包含在内；可控假模型测试不计入上方模型准确率。
- 前端：构建通过；16项测试与预录冒烟检查通过。
- Lint：无错误，保留4条原有组件警告；新增组件没有警告。
- 界面检查：两种模式可选、模型不可用显示复核、不可点击确认绕过、历史恢复使旧结论失效、下一步被禁用；截图见output/sag-app-preview.jpg。

代码在本机，真实模型调用只发送虚构材料。交付包不含密钥、.env、node_modules、.venv或用户材料／索引。启动和完整改进标准见[sag-grounding.md](sag-grounding.md)。原始结果见output/integration-live.json，可逐条复查原子事实和原文位置。
'''
    (ROOT/'docs/sag-validation.md').write_text(report,encoding='utf-8',newline='\n')
    manifest={'upstream_commit':'43416faf6b575b9f4d1afc9ae834e87e89a2cb61',
        'upstream_committed_at':'2026-10-22T12:15:03Z','engine':'zleap-sag==0.15.0',
        'python_tests':{'run':155,'passed':154,'skipped':1,'reason':'optional paddleocr missing'},
        'frontend_tests':16,'frontend_build':'passed','lint_errors':0,'existing_lint_warnings':4,
        'pilot_metrics':metrics,'independent_annotation':False,'real_user_documents_sent':False}
    (OUT/'validation-summary.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run(['git','add','--intent-to-add','--','.'],cwd=ROOT,check=True)
    subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
    (OUT/'integration.patch').write_bytes(subprocess.check_output(['git','diff','--binary','HEAD'],cwd=ROOT))
    names=set(subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0'))-{''}
    files=[ROOT/name for name in sorted(names)]
    files+=list((ROOT/'frontend/dist').rglob('*'))
    files += [OUT/name for name in ['integration-live.json','validation-summary.json','integration.patch','backend-tests.txt','sag-app-preview.jpg']]
    files=[p for p in files if p.is_file() and not p.is_symlink()]
    for p in files:
        if re.search(rb'sk-[A-Za-z0-9]{30,}',p.read_bytes()):
            raise SystemExit('Potential credential in '+str(p.relative_to(ROOT)))
    archive=ROOT.parent/'ApplyGuard-SAG集成实验版.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,arcname='applyguard-sag-app/'+p.relative_to(ROOT).as_posix())
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUT/'delivery.json').write_text(json.dumps({'archive':str(archive),'sha256':digest,
        'files':len(files),'size_bytes':archive.stat().st_size},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'archive':str(archive),'files':len(files),'bytes':archive.stat().st_size},ensure_ascii=False))

if __name__=='__main__':main()
