"""Every invocation writes a dated, immutable report, including failed attempts."""
import argparse,hashlib,io,json,platform,sys,time,traceback,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
ZONE=timezone(timedelta(hours=8),'Asia/Shanghai')

class RecordedResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.records=[];self.active={};self.subcases=0
    def startTest(self,test):
        super().startTest(test);self.active[test.id()]={'test':test.id(),'status':'PASS','started':time.monotonic(),'subcases':[]}
    def _mark(self,test,status,**details):
        if test.id() in self.active:
            self.active[test.id()].update(status=status,**details)
        else:
            # setUpClass/tearDownClass failures have no preceding startTest.
            self.records.append({'test':test.id(),'status':status,'fixture':True,
                                 'elapsed_seconds':0,'subcases':[],**details})
    def addFailure(self,test,err):super().addFailure(test,err);self._mark(test,'FAIL')
    def addError(self,test,err):super().addError(test,err);self._mark(test,'ERROR')
    def addSkip(self,test,reason):super().addSkip(test,reason);self._mark(test,'SKIP',reason=reason)
    def addSubTest(self,test,subtest,err):
        super().addSubTest(test,subtest,err);self.subcases+=1
        self.active[test.id()]['subcases'].append({'id':str(subtest),'status':'FAIL' if err else 'PASS'})
        if err:self.active[test.id()]['status']='FAIL'
    def stopTest(self,test):
        row=self.active.pop(test.id());row['elapsed_seconds']=round(time.monotonic()-row.pop('started'),6)
        self.records.append(row);super().stopTest(test)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);parser.add_argument('--all',action='store_true');parser.add_argument('modules',nargs='*');args=parser.parse_args()
    if not args.all and not args.modules:parser.error('Select modules or --all')
    started=datetime.now(ZONE);label=''.join(c if c.isalnum() or c in '-_' else '_' for c in args.label)
    directory=ROOT/'output/test-reports'/(started.strftime('%Y%m%d_%H%M%S_%f')+'_'+label);directory.mkdir(parents=True,exist_ok=False)
    files=sorted((ROOT/'backend').rglob('*.py'))+sorted((ROOT/'tests').glob('*.py'))+[Path(__file__).resolve()]
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests')) if args.all else unittest.defaultTestLoader.loadTestsFromNames(args.modules)
    log=io.StringIO();runner=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=RecordedResult)
    result=None;runner_error=None
    try:
        result=runner.run(suite)
    except Exception:
        runner_error=traceback.format_exc();log.write(runner_error)
    successful=result is not None and result.wasSuccessful() and not runner_error
    records=result.records if result is not None else []
    finished=datetime.now(ZONE)
    report={'started_at':started.isoformat(),'finished_at':finished.isoformat(),'timezone':'Asia/Shanghai',
        'label':label,'scope':'all backend tests' if args.all else args.modules,'python':platform.python_version(),
        'workspace_root':str(ROOT),'platform':platform.platform(),
        'status':'RUNNER_ERROR' if runner_error else 'PASS_WITH_SKIPS' if successful and result.skipped else 'PASS' if successful else 'FAIL',
        'methods':result.testsRun if result else None,'passed':sum(r['status']=='PASS' and not r.get('fixture') for r in records),
        'failed':sum(r['status'] in {'FAIL','ERROR'} and not r.get('fixture') for r in records),
        'fixture_errors':sum(r['status'] in {'FAIL','ERROR'} and r.get('fixture',False) for r in records),
        'skipped':len(result.skipped) if result else 0,'runner_error':runner_error,
        'parameter_subcases':result.subcases if result else None,'elapsed_seconds':(finished-started).total_seconds(),
        'source_sha256':manifest,'records':records,'note':'Methods, fixture errors and parameter subcases are separate; fake-model tests do not measure LLM factual accuracy.'}
    (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (directory/'test.log').write_text(log.getvalue(),encoding='utf-8')
    rows='\n'.join('| '+r['test']+' | '+r['status']+' | '+str(r['elapsed_seconds'])+' |' for r in records)
    md=f'''# 测试报告：{label}

- 日期时间：{started.isoformat()} — {finished.isoformat()}（北京时间）
- 范围：{report['scope']}
- 结果：{report['status']}；方法 {report['methods']}，通过 {report['passed']}，失败/错误 {report['failed']}，夹具错误 {report['fixture_errors']}，跳过 {report['skipped']}。
- 参数子用例：{report['parameter_subcases']}（不与测试方法相加冒充独立覆盖项）。
- 耗时：{report['elapsed_seconds']:.3f}秒。逐文件SHA256见report.json，完整执行信息见test.log。
- 限制：测试通过不等于无缺陷；模型桩测试不证明真实模型准确率。未执行项见测试计划。

| 测试 | 结果 | 秒 |
| --- | --- | ---: |
{rows}
'''
    (directory/'report.md').write_text(md,encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'records','source_sha256'}},ensure_ascii=False))
    print('REPORT '+str(directory));return 0 if successful else 1
if __name__=='__main__':raise SystemExit(main())
