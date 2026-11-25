"""Check the frozen MCP protocol, including while the desktop GUI is running. No model calls."""
import argparse
import asyncio
import json
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check(executable):
    async with stdio_client(StdioServerParameters(command=str(executable),args=['agent_mcp.py'])) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            names={tool.name for tool in (await session.list_tools()).tools}
            required={'get_task','search_materials','submit_evidence'}
            if not required.issubset(names):
                raise RuntimeError('Packaged MCP tools are missing')
            print(json.dumps({'protocol':'ok','tools':sorted(names),'model_calls':0}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    arguments=parser.parse_args()
    asyncio.run(asyncio.wait_for(check(arguments.exe.resolve(strict=True)),60))
