import json,os,sys,tempfile,threading,unittest
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from backend.app import ApplyGuardHandler as Handler
from backend.services import agent_bridge as a

class MCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_protocol_exact_quotes_and_revocation(self):
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'report.md').write_text('Atlas: Lin used SQL to evaluate 100 examples; 84 were correct.',encoding='utf8')
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url=f'http://127.0.0.1:{server.server_port}'
            c=a.create({'mode':'local','roots':[folder],'task':'Find Atlas evidence','disclosure':'cloud_allowed','purpose':'contribution'})
            params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).resolve().parents[1]/'scripts/agent_mcp.py')],env={**os.environ,
                'APPLYGUARD_AGENT_URL':url,'APPLYGUARD_AGENT_ID':c['id'],'APPLYGUARD_AGENT_TOKEN':c['token']})
            try:
                async with stdio_client(params) as (read,write):
                    async with ClientSession(read,write) as session:
                        await session.initialize()
                        self.assertEqual({t.name for t in (await session.list_tools()).tools},{'get_task','search_materials','submit_evidence'})
                        self.assertFalse((await session.call_tool('get_task',{})).isError)
                        found=await session.call_tool('search_materials',{'query':'Atlas'})
                        self.assertFalse(found.isError)
                        card=json.loads(found.content[0].text)['cards'][0]
                        args={'card_id':card['id'],'quote':card['quote'],'version':card['source']['version'],'experience':'Atlas','interpretation':'Candidate only','missing':['personal role needs review']}
                        self.assertFalse((await session.call_tool('submit_evidence',args)).isError)
                        self.assertEqual(a.GRANTS[c['id']]['cards'][card['id']]['state'],'NEEDS_REVIEW')
                        a.ui_call({**c,'action':'revoke'})
                        self.assertTrue((await session.call_tool('search_materials',{'query':'Atlas'})).isError)
            finally:server.shutdown();server.server_close();thread.join()

    async def test_http_unauthorized_ui_and_invalid_token(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            for path,headers in [('/ui',{}),('/ui',{'Origin':'https://evil.test','X-ApplyGuard-UI':'1'}),('/call',{'Authorization':'Bearer invalid'}),('/call',{'Origin':'http://localhost'})]:
                with self.subTest(path=path,headers=headers):
                    req=Request(f'http://127.0.0.1:{server.server_port}/api/v1/agent'+path,data=b'{}',headers=headers)
                    with self.assertRaises(HTTPError) as err:build_opener(ProxyHandler({})).open(req,timeout=5)
                    self.assertEqual(err.exception.code,422)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
