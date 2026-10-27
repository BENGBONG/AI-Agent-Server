"""Exercise real LiteLLM HTTP and SSE adapters against synthetic providers."""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest

from google.adk.models.llm_request import LlmRequest
from google.genai import types

from model_engines import EngineStore, PROVIDERS, engine_reference, use_engine_store
from model_engine_api import probe_engine
from model_runtime import ConfiguredEngine, configure_default_models


class ProviderHandler(BaseHTTPRequestHandler):
    paths = {"deepseek": "/deepseek/chat/completions", "kimi": "/kimi/v1/chat/completions",
             "openai": "/openai/v1/chat/completions", "claude": "/claude/v1/messages",
             "openrouter": "/openrouter/v1/chat/completions"}
    def log_message(self, *args):
        pass

    def do_GET(self):
        engine = self.path.split("/")[1]
        key = self.headers.get("x-api-key") if engine == "claude" else self.headers.get("authorization", "").removeprefix("Bearer ")
        if engine not in PROVIDERS or key != "synthetic-" + engine:
            self.send_error(401)
            return
        data = json.dumps({"data": [{"id": model} for model in PROVIDERS[engine]["models"]]})
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data.encode())

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        engine = self.path.split("/")[1]
        key = self.headers.get("x-api-key") if engine == "claude" else self.headers.get("authorization", "").removeprefix("Bearer ")
        self.server.requests.append({"engine": engine, "key": key, "path": self.path, "body": body})
        if self.path != self.paths.get(engine):
            self.send_error(404)
            return
        if key != "synthetic-" + engine:
            self.send_error(401)
            return
        model = body["model"]
        if engine == "claude":
            message = {"id": "msg_synthetic", "type": "message", "role": "assistant", "model": model, "content": [{"type": "text", "text": "OK"}], "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 5, "output_tokens": 1}}
            if body.get("stream"):
                start = {**message, "content": [], "stop_reason": None}
                events = [("message_start", {"type": "message_start", "message": start}),
                          ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
                          ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "OK"}}),
                          ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                          ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 1}}),
                          ("message_stop", {"type": "message_stop"})]
                payload = "".join("event: " + event + "\ndata: " + json.dumps(data) + "\n\n" for event, data in events)
            else:
                payload = json.dumps(message)
        else:
            base = {"id": "chatcmpl-synthetic", "created": 1, "model": model}
            if body.get("stream"):
                first = {**base, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "OK"}, "finish_reason": None}]}
                last = {**base, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}}
                payload = "data: " + json.dumps(first) + "\n\ndata: " + json.dumps(last) + "\n\ndata: [DONE]\n\n"
            else:
                payload = json.dumps({**base, "object": "chat.completion", "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}})
        self.send_response(200)
        self.send_header("content-type", "text/event-stream" if body.get("stream") else "application/json")
        self.send_header("content-length", str(len(payload.encode())))
        self.end_headers()
        self.wfile.write(payload.encode())


class ModelEngineTransportTest(unittest.TestCase):
    def test_five_provider_auth_protocols_probes_and_streaming_runtime(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
        server.requests = []
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as directory:
                store = EngineStore(Path(directory))
                port = server.server_address[1]
                for engine in PROVIDERS:
                    state = store.snapshot()
                    suffix = "" if engine == "deepseek" else "/v1"
                    store.save(engine, {"api_base": f"http://127.0.0.1:{port}/{engine}" + suffix, "models": state["engines"][engine]["models"]}, state["revision"], api_key="synthetic-" + engine)
                configure_default_models(store)

                async def check():
                    for engine in PROVIDERS:
                        with self.subTest(engine=engine):
                            settings = store.read()["engines"][engine]
                            result = await probe_engine(store, engine, settings, store.key(engine))
                            self.assertTrue(result["ok"])
                            with use_engine_store(store):
                                model = ConfiguredEngine(model=engine_reference(engine, settings["models"][0]))
                            request = LlmRequest(contents=[types.Content(role="user", parts=[types.Part(text="Reply OK")])])
                            output = [event async for event in model.generate_content_async(request, stream=True)]
                            text = "".join(part.text or "" for event in output if event.content for part in event.content.parts)
                            self.assertIn("OK", text)
                asyncio.run(check())
                self.assertEqual(len(server.requests), 10)
                for request in server.requests:
                    self.assertEqual(request["key"], "synthetic-" + request["engine"])
                    self.assertEqual(request["path"], ProviderHandler.paths[request["engine"]])
                    if request["engine"] != "deepseek":
                        self.assertNotIn("thinking", request["body"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
