"""Contract tests for DeepSeek's read-only web tools (no network calls)."""

import unittest
from unittest.mock import patch

import httpx

from shared_tools import web as web_tools


class WebToolsTest(unittest.IsolatedAsyncioTestCase):
    async def request(self, endpoint, payload, response):
        requests = []

        def handler(request):
            requests.append(request)
            return response

        transport = httpx.MockTransport(handler)
        real_client = httpx.AsyncClient
        with patch.object(web_tools, "_api_key", return_value="test-secret"), patch.object(
            web_tools.httpx, "AsyncClient",
            side_effect=lambda **kwargs: real_client(transport=transport, **kwargs),
        ):
            result = await web_tools._post(endpoint, payload)
        return result, requests

    async def test_search_keeps_sources_and_distinguishes_empty(self):
        with patch.object(web_tools, "_post", return_value={"results": [{
            "title": "Official", "url": "https://www.nfra.gov.cn/", "summary": "Summary",
            "date": "2026-10-22", "content": "unused",
        }]}) as post:
            result = await web_tools.deepseek_search("监管 官网", 3)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["results"][0]["url"], "https://www.nfra.gov.cn/")
        self.assertIn("retrieved_at", result)
        self.assertNotIn("content", result["results"][0])
        self.assertEqual(post.call_args.args[1], {"query": "监管 官网", "count": 3, "need_content": False})
        with patch.object(web_tools, "_post", return_value={"results": []}):
            self.assertEqual((await web_tools.deepseek_search("不存在"))["status"], "empty")

    async def test_validation_does_not_send_bad_inputs(self):
        with patch.object(web_tools, "_post") as post:
            for query, count in [(" ", 5), ("a" * 129, 5), ("query", 0), ("query", 11), ("query", True)]:
                self.assertEqual((await web_tools.deepseek_search(query, count))["status"], "error")
            for url in ["file:///etc/passwd", "http://127.0.0.1/", "http://[::1]/", "http://169.254.169.254/", "http://localhost/", "http://host.local/", "https://u:p@example.com/", "https://example.com:8000/", "https://example.com/?token=private", "not-a-url"]:
                self.assertEqual((await web_tools.deepseek_fetch(url))["status"], "error", url)
            post.assert_not_called()

    async def test_fetch_content_limit_and_malformed_payloads(self):
        with patch.object(web_tools, "_post", return_value={"title": "Page", "content": "x" * 25000}):
            result = await web_tools.deepseek_fetch("https://example.com/page#section")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["content"]), 20000)
        self.assertEqual(result["url"], "https://example.com/page")
        for payload in [{}, {"content": ""}, {"content": 123}, []]:
            with patch.object(web_tools, "_post", return_value=payload):
                self.assertEqual((await web_tools.deepseek_fetch("https://example.com"))["status"], "error")
        with patch.object(web_tools, "_post", return_value={"results": "bad"}):
            self.assertEqual((await web_tools.deepseek_search("query"))["status"], "error")

    async def test_http_auth_and_error_redaction(self):
        result, requests = await self.request("search", {"query": "hello"}, httpx.Response(200, json={"results": []}))
        self.assertEqual(result, {"results": []})
        self.assertEqual(str(requests[0].url), "https://api.deepseek.com/v1/tools/search")
        self.assertEqual(requests[0].headers["authorization"], "Bearer test-secret")
        for code in [401, 402, 429, 500]:
            with self.assertRaises(web_tools.WebToolError) as caught:
                await self.request("fetch", {"url": "https://example.com"}, httpx.Response(code, text="test-secret"))
            self.assertNotIn("test-secret", str(caught.exception))

    async def test_missing_key_timeout_and_non_json(self):
        with patch.object(web_tools, "_api_key", return_value=""), patch.object(web_tools.httpx, "AsyncClient") as client:
            result = await web_tools.deepseek_search("hello")
            self.assertEqual(result["error_code"], "missing_key")
            client.assert_not_called()
        with patch.object(web_tools, "_post", side_effect=web_tools.WebToolError("timeout", "请求超时")):
            result = await web_tools.deepseek_fetch("https://example.com")
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error_code"], "timeout")
        with self.assertRaises(web_tools.WebToolError):
            await self.request("search", {}, httpx.Response(200, text="not-json test-secret"))


if __name__ == "__main__":
    unittest.main()
