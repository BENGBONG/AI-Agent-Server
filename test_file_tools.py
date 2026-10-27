"""Synthetic document, session isolation, upload and vision contract coverage."""

from io import BytesIO
import json
import unittest
from unittest.mock import patch
import zipfile

from google.adk import Agent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext, FunctionTool
from google.genai import types
import httpx
from openpyxl import Workbook
from PIL import Image
import pymupdf

from shared_tools import files, vision
from shared_tools.document_parsers import DocumentError
from shared_tools.registry import bind_tools
from upload_handling import UploadedFilesPlugin


def png():
    output = BytesIO()
    Image.new("RGB", (160, 80), "white").save(output, "PNG")
    return output.getvalue()


def pdf(scanned=False, extra_page=False):
    with pymupdf.open() as document:
        page = document.new_page()
        if scanned:
            page.insert_image(pymupdf.Rect(30, 30, 300, 180), stream=png())
        else:
            page.insert_text((50, 70), "Demo statement: due 2026-11-01, total 1280.50 CNY.")
        if extra_page:
            document.new_page().insert_text((50, 70), "Second page.")
        return document.tobytes()


class FileToolsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.artifacts = InMemoryArtifactService()
        self.sessions = InMemorySessionService()
        session = await self.sessions.create_session(app_name="files_test", user_id="user_a")
        self.invocation = InvocationContext(
            session_service=self.sessions, invocation_id="files_inv", session=session,
            artifact_service=self.artifacts, agent=Agent(name="file_agent", tools=[files.parse_uploaded_file]),
        )
        self.context = ToolContext(self.invocation)

    async def save(self, name, data, mime="application/octet-stream", user="user_a"):
        await self.artifacts.save_artifact(app_name="files_test", user_id=user, session_id=self.invocation.session.id, filename=name, artifact=types.Part.from_bytes(data=data, mime_type=mime))

    async def test_text_csv_and_file_scope(self):
        await self.save("bill.csv", "机构,金额\n示例银行,1280.50\n".encode("gb18030"))
        await self.save("other.txt", b"private", user="user_b")
        listing = await files.list_uploaded_files(self.context)
        self.assertEqual(listing["files"], [{"filename": "bill.csv"}])
        result = await files.parse_uploaded_file("bill.csv", self.context)
        self.assertEqual(result["status"], "ok")
        self.assertIn("示例银行\t1280.50", result["sections"][0]["text"])
        self.assertFalse(result["verified"])
        for name in ["other.txt", "/etc/passwd", "../.env"]:
            self.assertEqual((await files.parse_uploaded_file(name, self.context))["error_code"], "file_not_found")

    async def test_text_and_csv_limits_are_explicit(self):
        await self.save("long.txt", ("账单" * 120000).encode())
        result = await files.parse_uploaded_file("long.txt", self.context)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["sections"][0]["text"]), 20000)
        self.assertTrue(result["sections"][0]["text"].startswith("账单"))
        await self.save("rows.csv", ("header\n" + "data\n" * 201).encode())
        self.assertTrue((await files.parse_uploaded_file("rows.csv", self.context))["truncated"])

    async def test_docx_and_xlsx_do_not_execute_formulas(self):
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>示例账单 1280.50</w:t></w:r></w:p></w:body></w:document>')
        await self.save("bill.docx", output.getvalue())
        self.assertIn("1280.50", (await files.parse_uploaded_file("bill.docx", self.context))["sections"][0]["text"])
        output = BytesIO()
        workbook = Workbook()
        workbook.active.append(["Amount", "Formula"])
        workbook.active.append([1280.50, "=SUM(A1:A2)"])
        workbook.save(output)
        workbook.close()
        await self.save("bill.xlsx", output.getvalue())
        result = await files.parse_uploaded_file("bill.xlsx", self.context)
        self.assertIn("=SUM(A1:A2)", result["sections"][0]["text"])
        self.assertTrue(any("公式" in message for message in result["warnings"]))

    async def test_pdf_text_pagination_and_cloud_opt_in(self):
        await self.save("text.pdf", pdf(extra_page=True))
        with patch.object(files, "transcribe_pages") as cloud:
            result = await files.parse_uploaded_file("text.pdf", self.context, max_pages=1)
            self.assertEqual(result["status"], "ok")
            self.assertIn("1280.50", result["sections"][0]["text"])
            self.assertTrue(result["truncated"])
            cloud.assert_not_called()
        await self.save("scan.pdf", pdf(scanned=True))
        with patch.object(files, "transcribe_pages", return_value=[{"unit": "page", "index": 1, "text": "Demo 1280.50", "method": "deepseek_flash_vision"}]) as cloud:
            pending = await files.parse_uploaded_file("scan.pdf", self.context)
            self.assertEqual(pending["status"], "needs_vision")
            cloud.assert_not_called()
            recognized = await files.parse_uploaded_file("scan.pdf", self.context, use_vision=True)
            self.assertEqual(recognized["status"], "ok")
            self.assertIn("1280.50", recognized["sections"][0]["text"])
            self.assertEqual(cloud.call_count, 1)
        self.assertEqual((await files.parse_uploaded_file("text.pdf", self.context, start_page=99))["error_code"], "invalid_page")

    async def test_image_failure_is_not_reported_as_success(self):
        await self.save("bill.png", png(), "image/png")
        with patch.object(files, "transcribe_pages", side_effect=DocumentError("vision_timeout", "识别超时")):
            result = await files.parse_uploaded_file("bill.png", self.context, use_vision=True)
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error_code"], "vision_timeout")
            self.assertEqual(result["pending_pages"], [1])

    async def test_invalid_documents_empty_and_parameters(self):
        # ADK's artifact loader treats a zero-byte payload as unavailable.
        for name, data, expected in [("empty.txt", b"", "file_not_found"), ("bad.pdf", b"%PDF-invalid", "invalid_document"), ("old.xls", b"old-format", "unsupported_format")]:
            await self.save(name, data)
            self.assertEqual((await files.parse_uploaded_file(name, self.context))["error_code"], expected)
        self.assertEqual((await files.parse_uploaded_file("x", self.context, max_pages=6))["error_code"], "invalid_input")
        await self.save("big.txt", b"123456")
        with patch("shared_tools.document_parsers.MAX_FILE_BYTES", 5):
            self.assertEqual((await files.parse_uploaded_file("big.txt", self.context))["error_code"], "file_limit")
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("word/document.xml", '<!DOCTYPE x [<!ENTITY e "unsafe">]><x>&e;</x>')
        await self.save("entities.docx", output.getvalue())
        self.assertEqual((await files.parse_uploaded_file("entities.docx", self.context))["error_code"], "invalid_document")

    async def test_conditional_upload_plugin_stores_file_without_forwarding_pdf(self):
        plugin = UploadedFilesPlugin()
        message = types.Content(role="user", parts=[types.Part(text="请解析"), types.Part(inline_data=types.Blob(data=pdf(), mime_type="application/pdf", display_name="demo.pdf"))])
        result = await plugin.on_user_message_callback(invocation_context=self.invocation, user_message=message)
        self.assertTrue(all(part.inline_data is None and part.file_data is None for part in result.parts))
        self.assertIn("demo.pdf", (await files.list_uploaded_files(self.context))["files"][0]["filename"])
        self.invocation.agent = Agent(name="without_file_tools")
        self.assertIsNone(await plugin.on_user_message_callback(invocation_context=self.invocation, user_message=message))

    async def test_upload_storage_failure_does_not_forward_raw_attachment(self):
        message = types.Content(role="user", parts=[types.Part(inline_data=types.Blob(data=pdf(), mime_type="application/pdf", display_name="demo.pdf"))])
        with patch.object(InMemoryArtifactService, "save_artifact", side_effect=OSError("synthetic storage error")), self.assertLogs(level="ERROR"):
            result = await UploadedFilesPlugin().on_user_message_callback(invocation_context=self.invocation, user_message=message)
        self.assertTrue(all(part.inline_data is None for part in result.parts))
        self.assertIn("保存失败", result.parts[0].text)

    async def test_generated_wrapper_injects_context_and_preserves_parameters(self):
        namespace = {"__name__": "example.tool_entries"}
        bind_tools(namespace, ["parse_uploaded_file", "list_uploaded_files"])
        schema = FunctionTool(namespace["parse_uploaded_file"])._get_declaration().parameters_json_schema
        self.assertNotIn("tool_context", schema["properties"])
        self.assertFalse(schema["properties"]["use_vision"]["default"])
        await self.save("test.txt", b"1280.50")
        result = await namespace["parse_uploaded_file"]("test.txt", self.context)
        self.assertEqual(result["status"], "ok")

    async def test_vision_transport_schema_and_error_redaction(self):
        requests = []
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"pages": [{"page": 1, "text": "1280.50", "uncertainties": []}]})}}]})
        real_client = httpx.AsyncClient
        with patch.object(vision, "read_deepseek_key", return_value="test-secret"), patch.object(vision.httpx, "AsyncClient", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)):
            pages = await vision.transcribe_pages([(1, png(), "image/png")])
        self.assertEqual(pages[0]["text"], "1280.50")
        self.assertEqual(requests[0]["model"], "deepseek-flash")
        self.assertEqual(requests[0]["messages"][0]["content"][-1]["type"], "image_url")
        def fail(request):
            return httpx.Response(401, text="test-secret")
        with patch.object(vision, "read_deepseek_key", return_value="test-secret"), patch.object(vision.httpx, "AsyncClient", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(fail), **kw)):
            with self.assertRaises(DocumentError) as error:
                await vision.transcribe_pages([(1, png(), "image/png")])
        self.assertNotIn("test-secret", str(error.exception))


if __name__ == "__main__":
    unittest.main()
