"""Bounded, offline HTTP checks against the user's local preview. No CV text is logged."""
import argparse
import http.client
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.test_resume_abnormal import body,pdf

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8870)
    parser.add_argument('--cv',type=Path)
    args=parser.parse_args()
    cases=[('object_mode',body(parse_mode={}),422),('array_mode',body(parse_mode=[]),422),
        ('broken_base64',body(pdf_base64='!invalid!'),422),('encrypted_pdf',body(pdf(encrypted=True)),422),
        ('damaged_pdf',body(b'%PDF-1.4\nbroken'),422),('unreadable_drawing',body(pdf(text='',drawing=True)),422),
        ('healthy_after_errors',body(),200)]
    if args.cv:cases.append(('local_cv',body(args.cv.read_bytes(),filename=args.cv.name),200))
    failed=0
    for name,payload,expected in cases:
        conn=http.client.HTTPConnection('127.0.0.1',args.port,timeout=15)
        try:
            conn.request('POST','/api/v1/resume/parse',json.dumps(payload).encode(),{'Content-Type':'application/json'})
            response=conn.getresponse();status=response.status;result=json.loads(response.read())
            ok=status==expected
            details={}
            if expected==422:ok=ok and result.get('error',{}).get('code')=='VALIDATION_ERROR'
            elif name=='healthy_after_errors':ok=ok and result.get('form',{}).get('basic',{}).get('email')=='fictional@example.test'
            else:
                form=result.get('form',{});basic=form.get('basic',{})
                details={'name_present':bool(basic.get('name')),'education':len(form.get('education',[])),
                    'projects':len(form.get('projects',[])),'awards':len(form.get('awards',[])),
                    'missing_personal_fields_still_blank':all(not basic.get(k) for k in ('phone','gender','city')),
                    'offline':result.get('extractor')=='规则抽取'}
                ok=ok and details=={'name_present':True,'education':1,'projects':10,'awards':3,
                    'missing_personal_fields_still_blank':True,'offline':True}
            failed+=not ok
            print(json.dumps({'case':name,'status':'PASS' if ok else 'FAIL','http_status':status,'expected':expected,**details},ensure_ascii=False))
        except Exception as exc:
            failed+=1
            print(json.dumps({'case':name,'status':'ERROR','exception_type':type(exc).__name__}))
        finally:conn.close()
    print(json.dumps({'cases':len(cases),'failed':failed,'scope':'localhost offline smoke; no browser or real model'},ensure_ascii=False))
    return 1 if failed else 0

if __name__=='__main__':raise SystemExit(main())
