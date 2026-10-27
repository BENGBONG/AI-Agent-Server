# AI-Agent-Server 外部调用接口文档

文档版本：2026-10-27。适用代码基线：`ce7df9b` 及本次文档提交。框架：Google ADK 2.12.0 / FastAPI；协议：HTTP JSON、SSE。接口路径目前没有 `/v1` 版本前缀。

本目录依据本项目运行服务的 `/openapi.json`、已安装 ADK 源码和项目自有路由整理，覆盖 **66 个 HTTP 路径、81 个 HTTP 操作**。此处的“外部调用”指业务代码作为客户端调用本服务；当前启动器只监听本机 `127.0.0.1:8000`，没有提供公网服务地址。

| 文件 / 入口 | 用途 |
| --- | --- |
| [完整端点参考](ENDPOINTS.md) | 全部 HTTP 操作的路径、参数、请求体、响应类型与访问范围 |
| [OpenAPI 3.1 定义](openapi.json) | 可供支持 OpenAPI 3.1 的 API 客户端导入；含完整嵌套数据类型 |
| [验证摘要](verification.json) | 文档结构、路由覆盖与隔离调用检查的完成及未覆盖范围 |
| `GET /openapi.json` | 运行服务自动生成的原始定义；自有无类型请求体和 SSE 类型不完整 |
| `GET /docs`、`GET /redoc` | 运行服务自带的接口浏览页面；使用原始定义 |

发布的 `openapi.json` 保留运行服务的全部 HTTP method/path，按源码补齐模型/MCP/Skill 管理的请求与响应，将 `/run_sse` 的成功响应修正为 `text/event-stream`，并对原生兼容路由重复的 operationId 做文档层去重；原 ID 保存在 `x-runtime-operation-id`。这些不修改服务端自动定义或运行实现。原始快照哈希、代码基线与补全范围记录在其 `x-documentation-source` 中。

## 1. 接入范围与访问方式

### 1.1 地址、请求头和身份

```text
HTTP Base URL: http://127.0.0.1:8000
JSON Content-Type: application/json
SSE Accept: text/event-stream
```

当前没有应用级 API Key、Bearer Token、登录会话或用户权限校验。**模型供应商的 Key 是后端调用模型的凭据，不是本服务的访问令牌**，不应在业务 `/run` 请求中传入。

`user_id` / JSON `userId` 由调用方提供，作为数据命名空间使用；它不是已验证身份。当前框架的 Host / Origin 检查不等于业务身份认证。来自同机服务端代码的请求可以不带 `Origin`；浏览器跨站请求会被拒绝，本项目没有配置跨站白名单。

| 范围 | 当前用途 | 接入边界 |
| --- | --- | --- |
| `business` | 应用发现、会话、Agent 运行、附件 | 业务客户端主要使用这组接口；仍受本机监听与来源检查约束 |
| `local-management` | 模型引擎、MCP、Skill、应用绑定 | 额外检查请求对端是 loopback、Host 为本机、Origin 同源，拒绝 `Sec-Fetch-Site: cross-site` |
| `development` | Builder、调试、评测、开发 UI、遥测 | 开发工具接口；部分写操作还拒绝代理/隧道转发来源 |
| `conditional` | 内存服务、Agent Identity、云部署 | 路由存在，但行为依赖服务或云环境配置；不能由路由存在推断能力可用 |

本轮没有改变监听地址、鉴权机制或 CORS 配置。远程业务系统的实际接入与部署需另外建立地址、身份和权限契约；本文件不声明这些已实现。

### 1.2 命名、时间、重试

- ADK 原生 JSON 使用 **camelCase**：`appName`、`userId`、`sessionId`、`newMessage`、`inlineData`；原生请求兼容对应 snake_case，响应仍按 camelCase 返回。
- 项目自有 `/capabilities/api/*` JSON 使用 **snake_case**：`api_base`、`api_key`、`default_model`、`server_id`。路径/查询参数按参考文档逐字填写。
- Event 的 `timestamp` 和 Session 的 `lastUpdateTime` 为 Unix 秒数；其他日期字段以其 schema 为准。客户端保存服务返回的 ID，不根据示意值推导格式。
- `/run` 和 `/run_sse` 没有业务幂等键、可靠消息去重或后台任务查询接口。同一会话的请求应顺序处理；不要在断流后自动重发上一条业务消息。
- `GET /version` 返回的是 ADK 与 Python 版本，和本文件的文档版本不是同一版本号。

## 2. 最小调用流程

以下均为合成请求，`integration-demo` 是客户端自定的演示命名空间。运行类请求会使用 Agent 已保存的模型和工具，可能产生模型/API 用量。

### 2.1 健康检查与应用发现

```bash
export ADK_BASE='http://127.0.0.1:8000'
curl -sS "$ADK_BASE/health"
curl -sS "$ADK_BASE/version"
curl -sS "$ADK_BASE/list-apps"
curl -sS "$ADK_BASE/apps/credit_manager/app-info"
```

`GET /health` 返回 `{"status":"ok"}`。`GET /list-apps` 默认返回应用名数组，`?detailed=true` 返回 `{"apps":[...]}`。发现结果应以当前环境为准；仓库中的正式业务应用是 `credit_manager`。

### 2.2 创建会话

**POST** `/apps/{app_name}/users/{user_id}/sessions`

```bash
curl -sS "$ADK_BASE/apps/credit_manager/users/integration-demo/sessions" \
  -H 'Content-Type: application/json' \
  --data '{"sessionId":"integration-session-001","state":{"locale":"zh-CN"}}'
```

```json
{
  "id": "integration-session-001",
  "appName": "credit_manager",
  "userId": "integration-demo",
  "state": {"locale": "zh-CN"},
  "events": [],
  "lastUpdateTime": 0
}
```

上例响应为结构示意，真实时间由服务填写。请求体可省略，或使用 `{}` 让服务生成会话 ID。自定义重复 ID 可能返回 `409`。`state`、`events`、`options` 的完整规则见 OpenAPI；业务接入通常只需 `sessionId` 和初始 `state`。

`events` 用于导入历史，不能伪造 ADK 保留的协议函数、`longRunningToolIds` 或非默认 `actions`。`options` 是传给当前 Session service 的参数，不是任意应用配置。

### 2.3 普通请求

**POST** `/run`

```bash
curl -sS "$ADK_BASE/run" \
  -H 'Content-Type: application/json' \
  --data '{
    "appName":"credit_manager",
    "userId":"integration-demo",
    "sessionId":"integration-session-001",
    "newMessage":{"role":"user","parts":[{"text":"你好"}]}
  }'
```

返回 **Event 数组**，不是单独的回答字符串，也不是 OpenAI Chat Completions 响应：

```json
[
  {
    "id": "event-demo-001",
    "invocationId": "invocation-demo-001",
    "author": "credit_manager",
    "content": {"role": "model", "parts": [{"text": "你好，请告诉我需要处理的问题。"}]},
    "actions": {"stateDelta": {}, "artifactDelta": {}, "requestedAuthConfigs": {}, "requestedToolConfirmations": {}}
  }
]
```

示意事件不穷举字段。实际数组还可能包含工具调用、工具结果、状态更新、附件更新或等待用户选择的事件。`/run` 会等本轮事件收集完成后返回；其 `streaming` 字段不会把响应转换成 SSE。

### 2.4 流式请求

**POST** `/run_sse`

```bash
curl -N -sS "$ADK_BASE/run_sse" \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  --data '{
    "appName":"credit_manager",
    "userId":"integration-demo",
    "sessionId":"integration-session-001",
    "streaming":true,
    "newMessage":{"role":"user","parts":[{"text":"现在北京时间几点？"}]}
  }'
```

```text
data: {"id":"event-demo-002","author":"credit_manager","partial":true,"content":{"role":"model","parts":[{"text":"当前"}]}}

data: {"id":"event-demo-003","author":"credit_manager","partial":false,"content":{"role":"model","parts":[{"text":"当前北京时间为工具返回的时间。"}]}}

```

- 响应是 `text/event-stream`。即使 `streaming:false`，也会以 SSE 帧返回，只是不启用模型增量输出。
- 每个 `data:` 帧里的 JSON 是一个 Event；流内异常也可能返回 `{"error":"...","error_details":{...}}`。客户端必须逐帧检查，不能仅看 HTTP `200`。
- 帧按空行分隔；一个网络 chunk 不一定等于一帧。本服务没有 `[DONE]` 结束标记，流结束表现为连接正常结束。
- `partial:true` 用于临时增量展示。最终模型事件可能包含完整文本，不要把它再接在全部增量文本后面形成重复回答；思考分片 `part.thought:true` 也不应直接作为最终正文。
- 发现 `longRunningToolIds` 时应进入等待用户交互状态。流结束本身不表示用户已经确认或业务完成。
- 内容与 `actions.artifactDelta` 可能被拆成两个 SSE 事件；内容为空的事件也可能有有效附件/状态信息。
- 客户端断开会触发尽力取消，但本框架没有单独的任务取消/回滚接口，不能据此推断已发出的工具操作被撤销。

## 3. 运行请求和事件契约

### 3.1 `/run` 与 `/run_sse` 请求字段

| 字段 | 类型 | 当前使用规则 |
| --- | --- | --- |
| `appName` | string | 本项目没有设置默认应用，实际调用必须提供；缺少时返回 `400` |
| `userId` | string | 必填；应与目标会话一致 |
| `sessionId` | string | 必填；先创建会话 |
| `newMessage` | Content | 普通对话和用户确认回传必须提供 |
| `streaming` | boolean | 默认 false；只在 `/run_sse` 中控制模型增量输出 |
| `stateDelta` | object | 可选；在此次调用中合并会话状态，不是模型参数 |
| `functionCallEventId` | string | 可选；原生交互组件会回传原事件 ID，不是恢复长任务的唯一依据 |
| `invocationId` | string | 高级恢复字段；普通用户选择可依据 FunctionResponse ID 匹配原调用。未启用可恢复 App 时，不支持只传此字段而不传新消息 |
| `customMetadata` | object | 可选；RunConfig 元数据，行为由框架和插件决定 |
| `serviceTier` | string | 供应商相关高级字段；不代表当前五个引擎都支持 |

`Content` 由 `role` 和 `parts` 组成。常用 Part 是 `{"text":"..."}`、`{"inlineData":{...}}` 或 `{"functionResponse":{...}}`。不同类型使用不同 Part。完整类型是 OpenAPI 中的 `Content`、`Part`、`FunctionCall` 和 `FunctionResponse`。

每次调用按 **Agent 已保存的模型** 执行；当前没有请求级 `engine` / `model` / `api_key` 覆写契约。引擎 Key 的更换需要走本机模型管理接口。

### 3.2 需要识别的响应字段

| 字段 | 含义 |
| --- | --- |
| `id` / `invocationId` / `author` | 事件、调用和事件发出者；不保证最后一条事件就是最终回答 |
| `content.parts[].text` | 模型或工具相关文本，结合角色与 partial 判断 |
| `content.parts[].functionCall` | 预测的工具调用，含 `id`、`name`、`args` |
| `content.parts[].functionResponse` | 工具返回，检查其 `response` 内的实际业务状态 |
| `longRunningToolIds` | 等待外部完成的工具调用 ID，包括用户确认 |
| `actions.stateDelta` | 此事件产生的状态变化；最终状态也可读取会话确认 |
| `actions.artifactDelta` | 文件名到新版本号的映射，用 Artifact API 读取文件 |
| `partial` / `turnComplete` / `finishReason` | 分片、回合和停止信息；字段可能省略 |
| `errorCode` / `errorMessage` | 框架或模型报告的错误；并非每种失败都填写它们 |

项目模型适配器的部分错误会转为模型文本事件，因此 HTTP `200`、有文本、存在工具返回都不能单独证明业务成功。

## 4. 用户选择与人工确认回传

`get_user_choice(options: list[str])` 是原生长运行工具，初次调用返回待选状态。外部客户端需自己显示选项、等待真实选择，再调用 `/run` 或 `/run_sse` 回传；当前没有独立的 `/confirm` 或 `/choices` HTTP 端点。

待选 Event 的关键结构：

```json
{
  "id": "event-choice-001",
  "invocationId": "invocation-choice-001",
  "author": "credit_manager",
  "longRunningToolIds": ["call-choice-001"],
  "content": {
    "role": "model",
    "parts": [{"functionCall": {"id":"call-choice-001","name":"get_user_choice","args":{"options":["继续","取消"]}}}]
  }
}
```

用户选“继续”后，向 **同一 app / user / session** 回传：

```json
{
  "appName": "credit_manager",
  "userId": "integration-demo",
  "sessionId": "integration-session-001",
  "functionCallEventId": "event-choice-001",
  "newMessage": {
    "role": "user",
    "parts": [{"functionResponse": {
      "id": "call-choice-001",
      "name": "get_user_choice",
      "response": {"result": "继续"}
    }}]
  }
}
```

`id` 必须取自服务返回的 FunctionCall，`name` 必须一致；示意 ID 不可直接用于真实会话。此 `response.result` 格式与原生自由文本/选择组件一致，并已验证可以继续原调用。不要把未选择、超时或默认预选自动回传为同意。

## 5. 会话和状态

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/apps/{app_name}/users/{user_id}/sessions` | 创建会话，推荐入口 |
| GET | 同上 | 列出此用户的会话 |
| GET | `/apps/{app_name}/users/{user_id}/sessions/{session_id}` | 读取状态与事件历史 |
| PATCH | 同上 | 更新状态，不运行 Agent |
| DELETE | 同上 | 删除会话，成功返回 `200` 和 JSON `null` |

PATCH 请求：

```json
{"stateDelta":{"preferred_language":"zh-CN","current_task":"bill-review"}}
```

`POST .../sessions/{session_id}` 是原生兼容旧入口，schema 已标记弃用；新接入统一使用创建会话请求中的 `sessionId`。

当前默认 Session service 使用 Agent 目录下的本机 SQLite；默认 Artifact service 使用本机文件存储。路径只是当前实现，不应作为外部数据访问接口。删除会话不提供“同时删除所有 Artifact、记忆和外部业务记录”的事务性保证。

## 6. 附件上传、下载和解析

### 6.1 独立上传一个 Artifact

**POST** `/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts`

```json
{
  "filename":"demo.txt",
  "artifact":{"inlineData":{"mimeType":"text/plain","displayName":"demo.txt","data":"c3ludGhldGljIGRvY3VtZW50"}},
  "customMetadata":{"source":"integration-demo"}
}
```

`data` 是标准 Base64，上例内容为合成文本。响应是 `ArtifactVersion`，包含 `version`、`canonicalUri` 等字段；不是普通 `{"filename":...}`。`canonicalUri` 不是已公开的下载 URL，外部客户端应继续使用 Artifact API。

| 方法 | 路径后缀（统一接在会话路径后） | 返回 |
| --- | --- | --- |
| GET | `/artifacts` | 文件名数组 |
| GET | `/artifacts/{artifact_name}` | 最新 Part JSON；可带 `?version=0` |
| GET | `/artifacts/{artifact_name}/versions` | 整数版本号数组 |
| GET | `/artifacts/{artifact_name}/versions/{version_id}` | 指定版本 Part JSON，version_id 可为整数或 `latest` |
| GET | `/artifacts/{artifact_name}/versions/{version_id}/metadata` | 指定版本元数据 |
| GET | `/artifacts/{artifact_name}/versions/metadata` | 版本元数据列表 |
| DELETE | `/artifacts/{artifact_name}` | 删除该名称的 Artifact，成功为 JSON `null` |

下载返回 **Part JSON**，常见内容位于 `inlineData.data`，客户端需 Base64 解码；接口不是直接的二进制文件流。文件名作为 URL path 时应正确编码；`/versions` 是框架路由结构，不应当作普通文件名后缀随意拼接。

### 6.2 在消息中上传

也可以在 `newMessage.parts` 中同时提交文本和 `inlineData`。当 Agent 已启用本项目文件工具时，`UploadedFilesPlugin` 将附件保存为当前会话 Artifact，再移除原始字节，交由文件工具读取；未启用这些工具的 Agent 没有这一保证，不应直接发送模型不支持的 PDF / Office 原始文件。

当前业务文件解析上限为单文件 **20 MiB**、单次返回文字 **20,000 字符**。PDF 默认每次 3 页、最多 5 页；XLSX 最多前 5 个工作表，每表 200 行、40 列。这些是工具层限制，不应理解为所有 HTTP 请求共享相同上传上限。

当前没有独立 HTTP `/upload`、`/parse` 或 `/tools/execute`。解析流程是上传 Artifact → 向 Agent 发消息 → Agent 调用 `list_uploaded_files` / `parse_uploaded_file`。图片和扫描页的可选识别仍使用 DeepSeek，相关用户确认应按上一节回传。

## 7. 本机模型引擎管理

以下接口均在 `/capabilities/api/models` 下，采用 snake_case JSON。模型配置 `revision` 必须从这一接口读取，不能用能力配置的版本代替。

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| GET | `/capabilities/api/models` | 返回引擎、候选模型、默认模型、revision 和 has_key；不返回 Key |
| PUT | `/capabilities/api/models/{engine}` | 保存连接和本机 Key |
| POST | `/capabilities/api/models/{engine}/test` | 测试草稿推理或读取模型列表，不保存 |
| PUT | `/capabilities/api/models/default` | 保存新 Agent 默认模型 |

`engine` 只接受 `deepseek`、`kimi`、`openai`、`claude`、`openrouter`。

保存示意，`revision` 必须替换为刚读取的模型状态版本：

```json
{
  "revision":"<GET /capabilities/api/models 返回的 revision>",
  "settings":{"api_base":"https://api.openai.com/v1","models":["gpt-4.1-mini"]},
  "api_key":"<你自己的 Key>",
  "clear_key":false
}
```

- `settings.api_base` 与 `settings.models` 必填；models 为 1–100 个模型 ID，重复项会去重。
- 空白、null 或省略 `api_key` 保留现有值；`clear_key:true` 清除本机保存值，环境变量仍可提供 Key。不能同时清除并填写非空 Key。
- 更换 API 主机时，若已有 Key，需重新输入对应 Key。Key 不写入 Agent YAML，不在 GET 状态中回显。
- `/test` 接受相同配置字段，另有 `purpose`：`inference` 为简短真实推理，`models` 仅读模型目录。它们都不保存草稿；OpenRouter 目录读取本身也不能证明 Key 能完成推理。
- 推理测试返回 `{"ok":true,"model":"...","message":"...","latency_ms":...}`；目录返回 `{"ok":true,"models":[...],"message":"...","latency_ms":...}`。模型列表可能含非对话模型，工具和业务能力需另外验证。
- `/default` 请求为 `{"revision":"...","reference":"engine/openai/gpt-4.1-mini"}`。reference 必须是已保存目录中的模型且已有 Key；新建 Agent 前刷新 ADK 页面，已明确选模型的 Agent 不迁移。

Agent 引用规则：旧 `deepseek-flash` / `deepseek-v4-pro` 保持兼容；新增模型使用 `engine/{engine}/{model-id}`，OpenRouter 例如 `engine/openrouter/openai/gpt-4.1-mini`。引擎保存只维护连接；修改具体 Agent 的引擎仍需保存其模型配置。

## 8. 本机 MCP、Skill 和能力绑定

先 **GET** `/capabilities/api/state`，读取能力配置专属 `revision`。每次成功写入/连接测试后都使用响应中的新 revision；不要连续复用旧值。

| 方法 | 路径 | 请求重点 |
| --- | --- | --- |
| PUT | `/capabilities/api/mcp/{sid}` | `revision` + `server`，server.id 与路径一致 |
| POST | `/capabilities/api/mcp/{sid}/test` | `revision`；测试已保存的服务，并写入发现的工具与时间 |
| POST | `/capabilities/api/skills` | `revision` + `files` + 可选 enabled，新建 Skill |
| POST | `/capabilities/api/skills/import?revision=...` | 原始 ZIP bytes，Content-Type 为 `application/zip`，不是 multipart |
| GET | `/capabilities/api/skills/{sid}?version=1` | 可省略 version 读取当前版本 |
| PUT | `/capabilities/api/skills/{sid}` | 与新建相同，ID 不变，发布新版本 |
| POST | `/capabilities/api/skills/{sid}/restore/{version}` | `revision`；恢复为新版本，不覆盖历史 |
| PUT | `/capabilities/api/agents/{agent_name}` | `revision` + `binding`，按应用绑定工具与 Skill |
| DELETE | `/capabilities/api/{kind}/{identifier}` | `revision`；kind 是 mcp 或 skills，被绑定时拒绝 |

MCP 服务对象：

```json
{
  "id":"example-mcp",
  "name":"示意 MCP 服务",
  "transport":"streamable_http",
  "url":"https://mcp.example.com/mcp",
  "token_env":"EXAMPLE_MCP_TOKEN",
  "auth_header":"Authorization",
  "auth_prefix":"Bearer ",
  "enabled":true
}
```

这是对象结构示意，不是本项目已接入的外部服务。`token_env` 是本机环境变量名，不是真实 Token。当前支持 Streamable HTTP / SSE，不支持 stdio 或 OAuth 配置向导。改变连接信息会清空旧工具发现结果，需要重测。保存、测试、绑定是三个不同步骤。

Skill 的 `files` 是相对路径到 UTF-8 文本或 Base64 对象的映射；二进制对象结构为 `{"encoding":"base64","data":"...","size":123}`。读取时返回 `metadata`、`files`、`versions`。包内需有有效 `SKILL.md`；最多 100 个有效文件、解压后总计 10 MiB，导入 ZIP 本身也不超过 10 MiB。不能使用绝对路径、`..` 或符号链接；更多文件约束以源码校验为准。

能力绑定请求示意：

```json
{
  "revision":"<GET /capabilities/api/state 返回的 revision>",
  "binding":{
    "mcp":[{"server_id":"example-mcp","tools":["example_tool"]}],
    "skills":["example-skill"]
  }
}
```

需先实际登记并测试 MCP、创建对应 Skill，再绑定到存在的应用。每个 MCP 服务必须显式选至少一个已发现工具；没有隐式“全部工具”。上限是每应用 30 个服务、50 个 Skill。绑定粒度是 **应用**，加载器将其装配到该应用的根 Agent 和子 Agent，不是独立子节点白名单。

保存后从下一次 invocation 生效，当前 invocation 保留其能力快照。新配置不等于业务规则已经补全；`docs/credit-skills-detailed-design-v1/` 的设计稿仍不自动成为运行包。

## 9. Agent 配置和内部开发接口

业务聊天只需要已存在的 Agent，不需要每次调用 Builder。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/dev/apps/{app_name}/builder?file_path=root_agent.yaml` | 读取 YAML，text/plain；可带 tmp=true 读取草稿 |
| POST | `/dev/apps/{app_name}/builder/save?tmp=false` | multipart/form-data，重复 `files` 字段提交应用相对路径 YAML/相关文件 |
| POST | `/dev/apps/{app_name}/builder/save?tmp=true` | 保存草稿 |
| POST | `/dev/apps/{app_name}/builder/cancel` | 放弃草稿，返回 boolean |
| GET | `/dev/apps/{app_name}/build_graph` | 编辑器配置图 JSON |

保存文件名需包含应用目录，例如 `credit_manager/root_agent.yaml`；修改已有 Agent 时先读取完整配置并保留其提示词、工具、子 Agent 和生成参数。Agent 保存不会自动提交尚未保存的 MCP/Skill 或模型连接配置。

调试、自动测试、评测、遥测和部署的全部路由也列在 [完整端点参考](ENDPOINTS.md)。其中 `/eval-sets` 与 `/eval_sets` 等原生兼容拼写会同时出现；不要推断它们可以任意互换。部署接口不是业务模型调用接口。

## 10. 实时连接与条件能力

| 接口 / 能力 | 当前状态 |
| --- | --- |
| WebSocket `/run_live` | 原生路由已注册，HTTP OpenAPI 不包含它；当前五引擎适配器未实现 `BaseLlm.connect`，不能作为已支持的语音/视频/双向实时接口使用 |
| PATCH `/apps/{app_name}/users/{user_id}/memory` | 请求 `{"sessionId":"..."}`，将会话交给配置的 Memory service；默认回退为 InMemoryMemoryService，无持久业务账本或长期记忆保证，也无独立 HTTP 记忆搜索接口 |
| POST `/agent-identity/finalize` | Google Agent Identity / IAM connector 相关 OAuth 收尾接口，依赖额外包、云端连接器和凭据；不等于本服务业务用户登录 |
| `/dev/apps/{app_name}/deploy/*` | 原生 Cloud Run / Agent Engine / GKE 部署路由；依赖对应云环境与工具，没有进行本项目部署验收 |

本项目的普通工具 `deepseek_search`、`deepseek_fetch`、`get_beijing_time`、`list_uploaded_files`、`parse_uploaded_file`，以及绑定后提供的 Skill/MCP 工具，都是 Agent 运行时工具。它们没有一一对应的公开 HTTP 调用路径。

## 11. 错误处理

| HTTP 状态 | 典型原因 | 客户端处理 |
| --- | --- | --- |
| 400 | 参数、模型引用、文件或绑定约束不满足 | 修正输入，不盲目重试 |
| 403 | Host / Origin / 本机管理限制 | 使用正确本机入口；不要把模型 Key 当作本服务鉴权 |
| 404 | 应用、会话、Artifact、Skill 或引擎不存在 | 核对当前命名空间和资源 |
| 409 | 会话 ID 重复、配置 revision 冲突、Skill 已存在或仍被引用 | 重新读取当前状态，再决定修改；不是自动覆盖 |
| 413 | 管理 JSON/ZIP 请求超过上限 | 缩小请求；ZIP 与工具附件限额不同 |
| 415 | 项目管理接口 Content-Type 不符 | JSON 使用 application/json；Skill 导入使用 application/zip |
| 422 | FastAPI 请求字段/路径类型验证失败 | 读取 detail 中的位置与原因 |
| 500 | 存储、配置、依赖或服务内部错误 | 保留调用上下文，检查服务端状态 |
| 502 | 模型管理测试的上游连接/推理失败 | 检查引擎地址、Key、权限和额度；该路径会返回归纳后的错误文本 |

普通接口错误通常是 `{"detail":"..."}`，FastAPI 422 的 detail 也可能是数组；原生全局来源检查还可能返回 text/plain 403。SSE 在响应开始后的异常可能是流内 JSON，而项目模型适配器也可能返回说明错误的模型文本。应分别处理传输、事件和工具业务状态。

## 12. 验证与维护

本次使用临时应用、合成会话/附件、模拟模型，验证了创建/查询/更新/删除会话、JSON Artifact 上传下载、普通与 SSE 调用、snake_case 兼容、`get_user_choice` 待选与 FunctionResponse 回传、错误码、同源限制、Skill 保存与应用绑定。没有调用真实模型、修改正式 Agent 或登记正式能力。本次文档验证不意味着 81 个 HTTP 操作都逐一执行，更不代表云部署或实时语音已经验收。

导出更新后的标准定义和完整参考：

```bash
python scripts/export_api_docs.py --base-url http://127.0.0.1:8000
```

离线重建可传 `--source <原始 OpenAPI JSON 文件>`。脚本只读取 OpenAPI，不读取业务会话、附件或已保存 Key。版本升级/路由改动后重新导出，并按当前源码复核本文的接入流程、访问限制和条件能力。

在已安装项目依赖的虚拟环境中验证文档：

```bash
.venv/bin/python scripts/check_api_docs.py
```

校验覆盖 JSON Schema、内部引用、operationId 唯一性、完整参考同步、示例 JSON 及本地链接。传入 `--runtime <原始定义文件>` 可检查路由集合；传入 `--metaschema <官方规范 JSON>` 可按 [OpenAPI 3.1 官方元规范](https://spec.openapis.org/oas/3.1/schema/2022-10-07)进一步验证整个文档结构。校验脚本不访问模型或修改服务。
