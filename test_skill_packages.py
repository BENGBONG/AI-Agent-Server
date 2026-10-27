"""Full ZIP round trips and real native ADK script execution, synthetic only."""

import asyncio
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import platform
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient
from google.adk import Agent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.code_executors.code_execution_utils import CodeExecutionInput
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext

from adk_web import create_app
from capabilities.runtime import BoundCapabilities
from capabilities.script_executor import SkillScriptExecutor, runtime_status
from capabilities.store import CapabilityStore, ConfigError


def package_files():
    return {
        "SKILL.md": b"---\nname: package-probe\ndescription: Synthetic package and script verification.\n---\n\nRun scripts/calculate.py for synthetic totals.\n",
        "references/rules.json": b'{"add": "1.25"}',
        "assets/template.bin": b"\x00\xff\x01TEMPLATE",
        "README.md": b"Synthetic package, no automatic installation.\n",
        "scripts/calculate.py": (
            "from decimal import Decimal\nimport json,argparse,os\nfrom pathlib import Path\n"
            "p=argparse.ArgumentParser();p.add_argument('--amount');a=p.parse_args()\n"
            "rules=json.loads(Path('references/rules.json').read_text())\n"
            "assert Path('assets/template.bin').read_bytes()==b'\\x00\\xff\\x01TEMPLATE'\n"
            "assert 'SYNTHETIC_SCRIPT_SECRET' not in os.environ\n"
            "value=str(Decimal(a.amount)+Decimal(rules['add']))\n"
            "Path('result.json').write_text(json.dumps({'total':value}))\n"
            "print('SCRIPT-TOTAL:'+value)\n"
        ).encode(),
        "scripts/echo.sh": b'printf "%s" "$1"\n',
        "scripts/fail.py": b"import sys\nprint('expected synthetic failure',file=sys.stderr)\nsys.exit(7)\n",
    }


def archive(files, prefix="package-probe/"):
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        for path, value in files.items(): z.writestr(prefix + path, value)
        z.writestr("__MACOSX/._package-probe", b"ignored metadata")
    return output.getvalue()


class FullPackageTest(unittest.TestCase):
    def test_zip_binary_script_api_edit_restore_roundtrip(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); agent=root/"package_agent"; agent.mkdir()
            (agent/"root_agent.yaml").write_text("name: package_agent\nmodel: deepseek-flash\nagent_class: LlmAgent\ninstruction: Synthetic.\n")
            with TestClient(create_app(root,reload_agents=False),base_url="http://127.0.0.1",client=("127.0.0.1",1234)) as client:
                state=client.get('/capabilities/api/state').json()
                response=client.post('/capabilities/api/skills/import',params={'revision':state['revision']},content=archive(package_files()),headers={'Content-Type':'application/zip'})
                self.assertEqual(response.status_code,200,response.text)
                state=response.json()
                self.assertIn('scripts/calculate.py',state['skills']['package-probe']['scripts'])
                item=client.get('/capabilities/api/skills/package-probe').json()
                binary=item['files']['assets/template.bin']
                self.assertEqual(base64.b64decode(binary['data']),package_files()['assets/template.bin'])
                item['files']['SKILL.md']+='\nEdited instructions.\n'
                changed=client.put('/capabilities/api/skills/package-probe',json={'revision':state['revision'],'files':item['files'],'enabled':True})
                self.assertEqual(changed.status_code,200,changed.text)
                state=changed.json()
                restored=client.post('/capabilities/api/skills/package-probe/restore/1',json={'revision':state['revision']})
                self.assertEqual(restored.status_code,200,restored.text)
                store=CapabilityStore(root)
                self.assertEqual(store.skill_files('package-probe'),package_files())
                self.assertFalse((root/'result.json').exists(), 'Import must not execute any script')
                self.assertEqual(store.read()['skills']['package-probe']['version'],3)
                obj=store.skill_object('package-probe')
                self.assertEqual(obj.resources.get_asset('template.bin'),package_files()['assets/template.bin'])

    def test_paths_scripts_and_binary_boundaries(self):
        with TemporaryDirectory() as directory:
            store=CapabilityStore(directory)
            for name, content in [('scripts/../escape.py',b'x'),('assets//alias.bin',b'x'),('scripts/file.py',b'\xff'),('.env',b'x'),('assets/x\n.bin',b'x')]:
                with self.subTest(name=name), self.assertRaises(ConfigError):
                    store.validate_skill_files({**package_files(),name:content})
            with self.assertRaises(ConfigError):
                store.validate_skill_files({**package_files(),'assets/dir':b'x','assets/dir/file.txt':b'x'})
            result=store.unpack_skill(archive(package_files()))
            self.assertEqual(result,package_files())


@unittest.skipUnless(platform.system()=='Darwin', 'macOS execution boundary probe; Docker tested separately on deployment')
class ExecutorBoundaryTest(unittest.TestCase):
    def test_environment_host_files_and_network_are_unavailable(self):
        with TemporaryDirectory() as directory:
            secret=Path(directory)/'synthetic-private.txt'; secret.write_text('SYNTHETIC-PRIVATE')
            code=("import os,socket\n"
                  "assert 'SYNTHETIC_SCRIPT_SECRET' not in os.environ\n"
                  f"try:\n open({str(secret)!r}).read()\nexcept PermissionError: pass\nelse: raise AssertionError('host file accessible')\n"
                  "try:\n socket.create_connection(('127.0.0.1',8000),timeout=.3)\nexcept PermissionError: pass\nelse: raise AssertionError('network permitted')\n"
                  "print('BOUNDARIES-OK')\n")
            with patch.dict(os.environ,{'SYNTHETIC_SCRIPT_SECRET':'must-not-inherit'}):
                result=SkillScriptExecutor().execute_code(None,CodeExecutionInput(code=code))
            self.assertEqual(result.exit_code,0,result.stderr)
            self.assertIn('BOUNDARIES-OK',result.stdout)

    def test_timeout_and_output_limit(self):
        result=SkillScriptExecutor(timeout_seconds=1).execute_code(None,CodeExecutionInput(code='while True: pass'))
        self.assertEqual(result.exit_code,124)
        self.assertIn('时间',result.stderr)
        result=SkillScriptExecutor().execute_code(None,CodeExecutionInput(code="print('x'*5000000)"))
        self.assertEqual(result.exit_code,124)
        self.assertIn('输出',result.stderr)


class NativeScriptToolTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=CapabilityStore(self.temp.name)
        state=self.store.save_skill(package_files(),self.store.snapshot()['revision'])
        self.store.binding('probe',{'mcp':[],'skills':['package-probe']},state['revision'])
        self.bound=BoundCapabilities(self.store,'probe')
        self.sessions=InMemorySessionService();self.artifacts=InMemoryArtifactService()
        self.session=await self.sessions.create_session(app_name='probe',user_id='synthetic')
        self.agent=Agent(name='probe',tools=[self.bound])
        self.invocation=InvocationContext(session_service=self.sessions,artifact_service=self.artifacts,session=self.session,agent=self.agent,invocation_id='script-probe')
        self.context=ToolContext(self.invocation)
        self.tools={tool.name:tool for tool in await self.bound.get_tools(self.context)}

    async def asyncTearDown(self): await self.bound.close()

    async def test_native_python_resources_arguments_and_generated_artifacts(self):
        await self.tools['load_skill'].run_async(args={'skill_name':'package-probe'},tool_context=self.context)
        with patch.dict(os.environ,{'SYNTHETIC_SCRIPT_SECRET':'must-not-inherit'}):
            result=await self.tools['run_skill_script'].run_async(args={'skill_name':'package-probe','file_path':'scripts/calculate.py','args':{'amount':'10.50'}},tool_context=self.context)
        self.assertEqual(result['status'],'success',result)
        self.assertIn('SCRIPT-TOTAL:11.75',result['stdout'])
        self.assertTrue(result.get('saved_artifacts'),result)
        artifact_names=await self.artifacts.list_artifact_keys(app_name='probe',user_id='synthetic',session_id=self.session.id)
        self.assertTrue(any('result.json' in key for key in artifact_names),artifact_names)

    async def test_native_shell_arguments_and_error_reporting(self):
        token='literal $(echo must-not-execute); text'
        result=await self.tools['run_skill_script'].run_async(args={'skill_name':'package-probe','file_path':'scripts/echo.sh','args':[token]},tool_context=self.context)
        self.assertEqual(result['status'],'success',result)
        self.assertEqual(result['stdout'],token)
        failed=await self.tools['run_skill_script'].run_async(args={'skill_name':'package-probe','file_path':'scripts/fail.py'},tool_context=self.context)
        self.assertEqual(failed['status'],'error',failed)
        missing=await self.tools['run_skill_script'].run_async(args={'skill_name':'package-probe','file_path':'scripts/missing.py'},tool_context=self.context)
        self.assertEqual(missing['error_code'],'SCRIPT_NOT_FOUND')
        self.store.binding('probe',{'mcp':[],'skills':[]},self.store.snapshot()['revision'])
        next_context=ToolContext(InvocationContext(session_service=self.sessions,session=self.session,agent=self.agent,invocation_id='after-unbind'))
        self.assertEqual(await self.bound.get_tools(next_context),[])


if __name__=='__main__': unittest.main()
