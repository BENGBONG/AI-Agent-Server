"""Capability management, native toolsets, isolation and lifecycle regression."""

import asyncio
from io import BytesIO
import json
from pathlib import Path
import socket
import stat
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient
from google.adk import Agent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models.llm_request import LlmRequest
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
from google.genai import types
from mcp.server.mcpserver import MCPServer
import uvicorn

from adk_web import create_app, DraftAwareAgentLoader
from capabilities.runtime import BoundCapabilities, CapabilityCleanupPlugin, discover_mcp, native_mcp
from capabilities.store import CapabilityStore, ConfigError, server_config


def skill(text="Return the synthetic marker BILL-VALIDATED."):
    return {"SKILL.md": ("---\nname: bill-review\ndescription: Synthetic bill review instructions.\n---\n\n" + text + "\n").encode(), "references/example.md": b"Synthetic amount: 1280.50 CNY.\n"}


def server(url="http://127.0.0.1:9001/mcp"):
    return dict(id="synthetic", name="Synthetic MCP", transport="streamable_http", url=url, token_env="", auth_header="Authorization", auth_prefix="Bearer ", enabled=True)


def app_fixture(root):
    folder = Path(root) / "capability_probe"
    folder.mkdir()
    (folder / "root_agent.yaml").write_text("name: capability_probe\nagent_class: LlmAgent\nmodel: deepseek-flash\ninstruction: Synthetic validation.\ntools:\n- name: get_user_choice\n")


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CapabilityStore(self.temp.name)

    def test_atomic_revision_and_explicit_tool_allowlist(self):
        rev = self.store.snapshot()["revision"]
        current = self.store.save_server(server(), rev)
        with self.assertRaises(ConfigError) as caught:
            self.store.save_server(server(), rev)
        self.assertEqual(caught.exception.status, 409)
        with self.assertRaises(ConfigError):
            self.store.binding("a", {"mcp":[{"server_id":"synthetic","tools":["echo"]}],"skills":[]}, current["revision"])
        current = self.store.discovered("synthetic", [{"name":"echo","description":"Synthetic echo"}], current["revision"])
        for tools in [[], ["unlisted"], ["echo", "echo"]]:
            with self.assertRaises(ConfigError):
                self.store.binding("a", {"mcp":[{"server_id":"synthetic","tools":tools}],"skills":[]}, current["revision"])
        current = self.store.binding("a", {"mcp":[{"server_id":"synthetic","tools":["echo"]}],"skills":[]}, current["revision"])
        with self.assertRaises(ConfigError):
            self.store.delete("mcp", "synthetic", current["revision"])
        self.assertEqual(json.loads(self.store.path.read_text())["agents"]["a"]["mcp"][0]["tools"], ["echo"])

    def test_server_validation_and_credential_references(self):
        for bad in [dict(url="file:///etc/passwd"),dict(url="https://user:secret@example.com/mcp"),dict(url="https://example.com/mcp?token=secret"),dict(transport="stdio"),dict(token_env="sk-actual-secret"),dict(auth_prefix="Bearer\n"),dict(auth_header="Host")]:
            with self.assertRaises(ConfigError):
                server_config({**server(), **bad})
        data = {**server(), "token_env":"SYNTHETIC_MCP_SECRET"}
        current = self.store.save_server(data, self.store.snapshot()["revision"])
        with patch.dict("os.environ", {"SYNTHETIC_MCP_SECRET":"synthetic-secret-value"}):
            toolset = native_mcp(self.store, current["mcp_servers"]["synthetic"], ["echo"])
        self.assertNotIn("synthetic-secret-value", json.dumps(current))
        self.assertIsNotNone(toolset)

    def test_skill_versions_restore_validation_and_archive(self):
        current = self.store.save_skill(skill(), self.store.snapshot()["revision"])
        self.assertEqual(current["skills"]["bill-review"]["version"], 1)
        with self.assertRaises(ConfigError):
            self.store.save_skill(skill(), current["revision"])
        current = self.store.save_skill(skill("Changed instructions."), current["revision"], expected_id="bill-review")
        self.assertEqual(current["skills"]["bill-review"]["version"], 2)
        current = self.store.save_skill(self.store.skill_files("bill-review", 1), current["revision"], expected_id="bill-review")
        self.assertEqual(current["skills"]["bill-review"]["version"], 3)
        self.assertIn("BILL-VALIDATED", self.store.skill_object("bill-review").instructions)
        current = self.store.save_skill({**skill(),"scripts/example.py":b"print('x')"}, current["revision"], expected_id="bill-review")
        self.assertIn("example.py", self.store.skill_object("bill-review").resources.list_scripts())
        with self.assertRaises(ConfigError):
            self.store.save_skill({**skill(),"../escape.md":b"x"}, current["revision"], expected_id="bill-review")
        self.store.delete("skills","bill-review",current["revision"])
        self.assertTrue((self.store.skills_dir / "bill-review/1/bill-review/SKILL.md").exists())

    def test_zip_containment_and_single_skill(self):
        def package(items):
            output = BytesIO()
            with zipfile.ZipFile(output,"w") as archive:
                for name,value in items.items(): archive.writestr(name,value)
            return output.getvalue()
        files = self.store.unpack_skill(package({"bill-review/"+k:v for k,v in skill().items()}))
        self.assertEqual(files,skill())
        for items in [{"../SKILL.md":b"x"},{"a/SKILL.md":b"x","b/SKILL.md":b"x"}]:
            with self.assertRaises(ConfigError): self.store.unpack_skill(package(items))
        output = BytesIO()
        with zipfile.ZipFile(output,"w") as archive:
            item=zipfile.ZipInfo("SKILL.md"); item.create_system=3; item.external_attr=(stat.S_IFLNK|0o777)<<16
            archive.writestr(item,"/etc/passwd")
        with self.assertRaises(ConfigError): self.store.unpack_skill(output.getvalue())


class ManagementApiTest(unittest.TestCase):
    def test_ui_api_same_origin_and_binding_persistence(self):
        with TemporaryDirectory() as root:
            app_fixture(root)
            application=create_app(Path(root),reload_agents=False)
            with TestClient(application,base_url="http://127.0.0.1",client=("127.0.0.1",10000)) as client:
                page=client.get("/capabilities")
                self.assertEqual(page.status_code,200)
                self.assertIn("Agent 能力管理",page.text)
                self.assertIn("frame-ancestors 'self'",page.headers["content-security-policy"])
                self.assertEqual(client.get("/capabilities/assets/app.js").status_code,200)
                self.assertEqual(client.get("/capabilities/assets/secret.env").status_code,404)
                self.assertEqual(client.get("/capabilities/api/state",headers={"Origin":"https://other.example"}).status_code,403)
                state=client.get("/capabilities/api/state").json()
                self.assertEqual(state["agent_names"],["capability_probe"])
                original=(Path(root)/"capability_probe/root_agent.yaml").read_bytes()
                response=client.post("/capabilities/api/skills",json={"revision":state["revision"],"files":{k:v.decode() for k,v in skill().items()}})
                self.assertEqual(response.status_code,200,response.text)
                state=response.json()
                response=client.put("/capabilities/api/agents/capability_probe",json={"revision":state["revision"],"binding":{"mcp":[],"skills":["bill-review"]}})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual((Path(root)/"capability_probe/root_agent.yaml").read_bytes(),original)
                self.assertEqual(client.get("/capabilities/api/skills/bill-review").json()["metadata"]["version"],1)
                self.assertEqual(client.put("/capabilities/api/agents/unknown",json={}).status_code,404)
                self.assertEqual(client.put("/capabilities/api/mcp/synthetic",json={"server":server()}).status_code,409)
                self.assertEqual(client.get("/dev/apps/capability_probe/build_graph").status_code,200)
                self.assertEqual(client.get("/dev/apps/capability_probe/builder").status_code,200)
                self.assertEqual(CapabilityStore(root).snapshot()["agents"]["capability_probe"]["skills"],["bill-review"])
            with TestClient(application,base_url="http://127.0.0.1",client=("192.0.2.1",10000)) as client:
                self.assertEqual(client.get("/capabilities/api/state").status_code,403)


class NativeToolsetsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=CapabilityStore(self.temp.name)
        self.sessions=InMemorySessionService()
        self.session=await self.sessions.create_session(app_name="probe",user_id="synthetic")
        self.bound=BoundCapabilities(self.store,"probe")
        self.agent=Agent(name="probe",tools=[self.bound])

    def context(self,invocation_id):
        invocation=InvocationContext(session_service=self.sessions,session=self.session,invocation_id=invocation_id,agent=self.agent)
        return invocation, ToolContext(invocation)

    async def test_skill_native_loading_snapshot_and_cleanup(self):
        current=self.store.save_skill(skill(),self.store.snapshot()["revision"])
        self.store.binding("probe",{"mcp":[],"skills":["bill-review"]},current["revision"])
        invocation,context=self.context("first")
        tools=await self.bound.get_tools(context)
        # ADK advertises execution only when an enabled Skill has scripts.
        self.assertEqual({x.name for x in tools},{"list_skills","load_skill","load_skill_resource"})
        loaded=await next(x for x in tools if x.name=="load_skill").run_async(args={"skill_name":"bill-review"},tool_context=context)
        self.assertIn("BILL-VALIDATED",loaded["instructions"])
        request=LlmRequest(model="deepseek-flash")
        await self.bound.process_llm_request(tool_context=context,llm_request=request)
        self.assertIn("get_user_choice",str(request.config.system_instruction))
        self.store.binding("probe",{"mcp":[],"skills":[]},self.store.snapshot()["revision"])
        self.assertTrue(await self.bound.get_tools(context))
        _,next_context=self.context("second")
        self.assertEqual(await self.bound.get_tools(next_context),[])
        await CapabilityCleanupPlugin().after_run_callback(invocation_context=invocation)
        self.assertNotIn("first",self.bound.bundles)
        invocation,_=self.context("second")
        await CapabilityCleanupPlugin().on_run_error_callback(invocation_context=invocation,error=RuntimeError("synthetic"))
        self.assertFalse(self.bound.bundles)

    async def test_real_mcp_discovery_filter_prefix_call_and_cleanup(self):
        sock=socket.socket(); sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]; sock.close()
        mcp=MCPServer("Synthetic capability test",log_level="ERROR")
        @mcp.tool()
        def echo(value:str)->str: return "SYNTHETIC:"+value
        @mcp.tool()
        def excluded()->str: return "must not be exposed"
        service=uvicorn.Server(uvicorn.Config(mcp.streamable_http_app(),host="127.0.0.1",port=port,log_level="error"))
        thread=threading.Thread(target=service.run,daemon=True); thread.start()
        try:
            for _ in range(100):
                if service.started: break
                await asyncio.sleep(.02)
            self.assertTrue(service.started)
            value=server(f"http://127.0.0.1:{port}/mcp")
            current=self.store.save_server(value,self.store.snapshot()["revision"])
            discovered=await discover_mcp(self.store,value)
            self.assertEqual({x["name"] for x in discovered},{"echo","excluded"})
            current=self.store.discovered("synthetic",discovered,current["revision"])
            self.store.binding("probe",{"mcp":[{"server_id":"synthetic","tools":["echo"]}],"skills":[]},current["revision"])
            invocation,context=self.context("mcp-first")
            tools=await self.bound.get_tools(context)
            self.assertEqual([x.name for x in tools],["mcp_synthetic_echo"])
            result=await tools[0].run_async(args={"value":"OK"},tool_context=context)
            self.assertIn("SYNTHETIC:OK",json.dumps(result,default=str))
            await CapabilityCleanupPlugin().after_run_callback(invocation_context=invocation)
            self.assertFalse(self.bound.bundles)
        finally:
            await self.bound.close()
            service.should_exit=True
            await asyncio.to_thread(thread.join,3)


if __name__=="__main__": unittest.main()
