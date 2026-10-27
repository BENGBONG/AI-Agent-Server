"""Mount the source-maintained capability UI inside the shipped ADK page."""

from fastapi.responses import Response


def install_adk_integration(app):
    @app.middleware("http")
    async def extend_adk_document(request, call_next):
        document = request.method == "GET" and request.url.path in {"/dev-ui/", "/dev-ui/index.html"}
        if document:
            # Installed StaticFiles uses an unchanged file ETag. Never let an
            # old cached pre-extension document produce a misleading 304.
            request.scope["headers"] = [(key, value) for key, value in request.scope["headers"]
                                        if key.lower() not in {b"if-none-match", b"if-modified-since"}]
        response = await call_next(request)
        if (not document
                or response.status_code != 200
                or "text/html" not in response.headers.get("content-type", "")):
            return response
        # Process only the HTML document, after native ADK request checks.
        # Keep installed assets untouched; never buffer SSE or API responses.
        body = b"".join([chunk async for chunk in response.body_iterator])
        extension = (
            b'<link rel="stylesheet" href="/capabilities/assets/adk-integration.css">'
            b'<script defer src="/capabilities/assets/adk-integration.js"></script>'
            b'<script defer src="/capabilities/assets/model-thinking.js"></script>'
        )
        body = body.replace(b"</head>", extension + b"</head>", 1)
        headers = {key: value for key, value in response.headers.items()
                   if key.lower() not in {"content-length", "etag", "last-modified"}}
        headers["cache-control"] = "no-store"
        return Response(body, status_code=response.status_code, headers=headers,
                        background=response.background)
