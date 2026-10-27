# 完整 HTTP 接口参考

本文件由 `scripts/export_api_docs.py` 生成；业务接入流程见 [接入指南](README.md)，完整嵌套类型见 [OpenAPI 3.1](openapi.json)。

共 66 个路径、81 个 HTTP 操作。WebSocket `/run_live` 的当前限制见接入指南，不计入 HTTP 数量。

范围：business＝业务调用；local-management＝本机同源配置；development＝开发 UI/调试；conditional＝需要额外服务或云配置。所有接口仍受当前监听地址与来源检查约束。

## 端点索引

| 方法 | 路径 | 分类 | 范围 |
| --- | --- | --- | --- |
| GET | [`/health`](#op-health_health_get) | System | business |
| GET | [`/version`](#op-version_version_get) | System | business |
| POST | [`/agent-identity/finalize`](#op-finalize_agent_identity_credentials_agent_identity_finalize_post) | Agent Identity | conditional |
| GET | [`/list-apps`](#op-list_apps_list_apps_get) | Applications | business |
| GET | [`/apps/{app_name}/app-info`](#op-get_adk_app_info_apps__app_name__app_info_get) | Applications | business |
| GET | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}`](#op-get_session_apps__app_name__users__user_id__sessions__session_id__get) | Sessions | business |
| POST | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}`](#op-create_session_with_id_apps__app_name__users__user_id__sessions__session_id__post) | Sessions | business |
| DELETE | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}`](#op-delete_session_apps__app_name__users__user_id__sessions__session_id__delete) | Sessions | business |
| PATCH | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}`](#op-update_session_apps__app_name__users__user_id__sessions__session_id__patch) | Sessions | business |
| GET | [`/apps/{app_name}/users/{user_id}/sessions`](#op-list_sessions_apps__app_name__users__user_id__sessions_get) | Sessions | business |
| POST | [`/apps/{app_name}/users/{user_id}/sessions`](#op-create_session_apps__app_name__users__user_id__sessions_post) | Sessions | business |
| GET | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}/versions/{version_id}/metadata`](#op-get_artifact_version_metadata_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions__version_id__metadata_get) | Artifacts | business |
| GET | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}/versions/metadata`](#op-list_artifact_versions_metadata_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions_metadata_get) | Artifacts | business |
| POST | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts`](#op-save_artifact_apps__app_name__users__user_id__sessions__session_id__artifacts_post) | Artifacts | business |
| GET | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts`](#op-list_artifact_names_apps__app_name__users__user_id__sessions__session_id__artifacts_get) | Artifacts | business |
| GET | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}/versions/{version_id}`](#op-load_artifact_version_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions__version_id__get) | Artifacts | business |
| GET | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}/versions`](#op-list_artifact_versions_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions_get) | Artifacts | business |
| GET | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}`](#op-load_artifact_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__get) | Artifacts | business |
| DELETE | [`/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}`](#op-delete_artifact_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__delete) | Artifacts | business |
| PATCH | [`/apps/{app_name}/users/{user_id}/memory`](#op-patch_memory_apps__app_name__users__user_id__memory_patch) | Memory | conditional |
| POST | [`/run`](#op-run_agent_run_post) | Agent invocation | business |
| POST | [`/run_sse`](#op-run_agent_sse_run_sse_post) | Agent invocation | business |
| GET | [`/dev-ui/assets/config/runtime-config.json`](#op-get_runtime_config_dev_ui_assets_config_runtime_config_json_get) | Web UI and telemetry | development |
| GET | [`/dev-ui/config`](#op-get_ui_config_dev_ui_config_get) | Web UI and telemetry | development |
| GET | [`/`](#op-redirect_root_to_dev_ui__get) | Web UI and telemetry | development |
| GET | [`/dev-ui`](#op-redirect_dev_ui_add_slash_dev_ui_get) | Web UI and telemetry | development |
| GET | [`/config/telemetry`](#op-get_telemetry_consent_config_telemetry_get) | Web UI and telemetry | development |
| POST | [`/config/telemetry`](#op-set_telemetry_consent_config_telemetry_post) | Web UI and telemetry | development |
| POST | [`/dev/apps/{app_name}/builder/save`](#op-builder_build_dev_apps__app_name__builder_save_post) | Builder | development |
| POST | [`/dev/apps/{app_name}/builder/cancel`](#op-builder_cancel_dev_apps__app_name__builder_cancel_post) | Builder | development |
| GET | [`/dev/apps/{app_name}/builder`](#op-get_agent_builder_dev_apps__app_name__builder_get) | Builder | development |
| GET | [`/dev/apps/{app_name}/debug/trace/{event_id}`](#op-get_trace_dict_dev_apps__app_name__debug_trace__event_id__get) | Debug | development |
| GET | [`/dev/apps/{app_name}/debug/trace/session/{session_id}`](#op-get_session_trace_dev_apps__app_name__debug_trace_session__session_id__get) | Debug | development |
| GET | [`/dev/apps/{app_name}/build_graph`](#op-get_app_info_dev_apps__app_name__build_graph_get) | Builder | development |
| GET | [`/dev/apps/{app_name}/build_graph_image`](#op-get_app_info_image_dev_apps__app_name__build_graph_image_get) | Builder | development |
| GET | [`/dev/apps/{app_name}/tests`](#op-list_tests_dev_apps__app_name__tests_get) | Agent tests | development |
| POST | [`/dev/apps/{app_name}/tests/rebuild`](#op-rebuild_app_tests_dev_apps__app_name__tests_rebuild_post) | Agent tests | development |
| POST | [`/dev/apps/{app_name}/tests/run`](#op-run_app_tests_dev_apps__app_name__tests_run_post) | Agent tests | development |
| PUT | [`/dev/apps/{app_name}/tests/{test_name}`](#op-create_test_dev_apps__app_name__tests__test_name__put) | Agent tests | development |
| DELETE | [`/dev/apps/{app_name}/tests/{test_name}`](#op-delete_test_dev_apps__app_name__tests__test_name__delete) | Agent tests | development |
| GET | [`/dev/apps/{app_name}/tests/{test_name}`](#op-get_test_content_dev_apps__app_name__tests__test_name__get) | Agent tests | development |
| POST | [`/dev/apps/{app_name}/eval-sets`](#op-create_eval_set_dev_apps__app_name__eval_sets_post) | Evaluation | development |
| GET | [`/dev/apps/{app_name}/eval-sets`](#op-list_eval_sets_dev_apps__app_name__eval_sets_get) | Evaluation | development |
| POST | [`/dev/apps/{app_name}/eval_sets/{eval_set_id}`](#op-create_eval_set_legacy_dev_apps__app_name__eval_sets__eval_set_id__post) | Evaluation | development |
| GET | [`/dev/apps/{app_name}/eval_sets`](#op-list_eval_sets_legacy_dev_apps__app_name__eval_sets_get) | Evaluation | development |
| POST | [`/dev/apps/{app_name}/eval_sets/{eval_set_id}/run_eval`](#op-run_eval_legacy_dev_apps__app_name__eval_sets__eval_set_id__run_eval_post) | Evaluation | development |
| GET | [`/dev/apps/{app_name}/eval_results/{eval_result_id}`](#op-get_eval_result_legacy_dev_apps__app_name__eval_results__eval_result_id__get) | Evaluation | development |
| GET | [`/dev/apps/{app_name}/eval_results`](#op-list_eval_results_legacy_dev_apps__app_name__eval_results_get) | Evaluation | development |
| POST | [`/dev/apps/{app_name}/eval_sets/{eval_set_id}/add_session`](#op-add_session_to_eval_set_dev_apps__app_name__eval_sets__eval_set_id__add_session_post__c786ed2b) | Evaluation | development |
| POST | [`/dev/apps/{app_name}/eval-sets/{eval_set_id}/add-session`](#op-add_session_to_eval_set_dev_apps__app_name__eval_sets__eval_set_id__add_session_post__5c8b5092) | Evaluation | development |
| GET | [`/dev/apps/{app_name}/eval_sets/{eval_set_id}/evals`](#op-list_evals_in_eval_set_dev_apps__app_name__eval_sets__eval_set_id__evals_get) | Evaluation | development |
| GET | [`/dev/apps/{app_name}/eval_sets/{eval_set_id}/evals/{eval_case_id}`](#op-get_eval_dev_apps__app_name__eval_sets__eval_set_id__evals__eval_case_id__get) | Evaluation | development |
| PUT | [`/dev/apps/{app_name}/eval_sets/{eval_set_id}/evals/{eval_case_id}`](#op-update_eval_dev_apps__app_name__eval_sets__eval_set_id__evals__eval_case_id__put) | Evaluation | development |
| DELETE | [`/dev/apps/{app_name}/eval_sets/{eval_set_id}/evals/{eval_case_id}`](#op-delete_eval_dev_apps__app_name__eval_sets__eval_set_id__evals__eval_case_id__delete) | Evaluation | development |
| GET | [`/dev/apps/{app_name}/eval-sets/{eval_set_id}/eval-cases/{eval_case_id}`](#op-get_eval_dev_apps__app_name__eval_sets__eval_set_id__eval_cases__eval_case_id__get) | Evaluation | development |
| PUT | [`/dev/apps/{app_name}/eval-sets/{eval_set_id}/eval-cases/{eval_case_id}`](#op-update_eval_dev_apps__app_name__eval_sets__eval_set_id__eval_cases__eval_case_id__put) | Evaluation | development |
| DELETE | [`/dev/apps/{app_name}/eval-sets/{eval_set_id}/eval-cases/{eval_case_id}`](#op-delete_eval_dev_apps__app_name__eval_sets__eval_set_id__eval_cases__eval_case_id__delete) | Evaluation | development |
| POST | [`/dev/apps/{app_name}/eval-sets/{eval_set_id}/run`](#op-run_eval_dev_apps__app_name__eval_sets__eval_set_id__run_post) | Evaluation | development |
| GET | [`/dev/apps/{app_name}/eval-results/{eval_result_id}`](#op-get_eval_result_dev_apps__app_name__eval_results__eval_result_id__get) | Evaluation | development |
| GET | [`/dev/apps/{app_name}/eval-results`](#op-list_eval_results_dev_apps__app_name__eval_results_get) | Evaluation | development |
| GET | [`/dev/apps/{app_name}/metrics-info`](#op-list_metrics_info_dev_apps__app_name__metrics_info_get) | Debug | development |
| GET | [`/dev/apps/{app_name}/graph`](#op-get_app_graph_dot_dev_apps__app_name__graph_get) | Debug | development |
| GET | [`/dev/apps/{app_name}/users/{user_id}/sessions/{session_id}/events/{event_id}/graph`](#op-get_event_graph_dev_apps__app_name__users__user_id__sessions__session_id__events__event_id__graph_get) | Debug | development |
| GET | [`/dev/apps/{app_name}/deploy/defaults`](#op-get_deploy_defaults_dev_apps__app_name__deploy_defaults_get) | Cloud deployment | conditional |
| POST | [`/dev/apps/{app_name}/deploy/agent_engine`](#op-deploy_to_agent_engine_dev_apps__app_name__deploy_agent_engine_post) | Cloud deployment | conditional |
| POST | [`/dev/apps/{app_name}/deploy/cloud_run`](#op-deploy_to_cloud_run_dev_apps__app_name__deploy_cloud_run_post) | Cloud deployment | conditional |
| POST | [`/dev/apps/{app_name}/deploy/gke`](#op-deploy_to_gke_dev_apps__app_name__deploy_gke_post) | Cloud deployment | conditional |
| GET | [`/capabilities/api/state`](#op-state_capabilities_api_state_get) | MCP and Skills | local-management |
| PUT | [`/capabilities/api/mcp/{sid}`](#op-save_server_capabilities_api_mcp__sid__put) | MCP and Skills | local-management |
| POST | [`/capabilities/api/mcp/{sid}/test`](#op-test_server_capabilities_api_mcp__sid__test_post) | MCP and Skills | local-management |
| DELETE | [`/capabilities/api/{kind}/{identifier}`](#op-remove_capabilities_api__kind___identifier__delete) | MCP and Skills | local-management |
| POST | [`/capabilities/api/skills/import`](#op-import_skill_capabilities_api_skills_import_post) | MCP and Skills | local-management |
| POST | [`/capabilities/api/skills`](#op-create_skill_capabilities_api_skills_post) | MCP and Skills | local-management |
| GET | [`/capabilities/api/skills/{sid}`](#op-read_skill_capabilities_api_skills__sid__get) | MCP and Skills | local-management |
| PUT | [`/capabilities/api/skills/{sid}`](#op-update_skill_capabilities_api_skills__sid__put) | MCP and Skills | local-management |
| POST | [`/capabilities/api/skills/{sid}/restore/{version}`](#op-restore_skill_capabilities_api_skills__sid__restore__version__post) | MCP and Skills | local-management |
| PUT | [`/capabilities/api/agents/{agent_name}`](#op-bind_agent_capabilities_api_agents__agent_name__put) | MCP and Skills | local-management |
| GET | [`/capabilities/api/models`](#op-state_capabilities_api_models_get) | Model engines | local-management |
| PUT | [`/capabilities/api/models/default`](#op-default_capabilities_api_models_default_put) | Model engines | local-management |
| PUT | [`/capabilities/api/models/{engine}`](#op-save_capabilities_api_models__engine__put) | Model engines | local-management |
| POST | [`/capabilities/api/models/{engine}/test`](#op-test_capabilities_api_models__engine__test_post) | Model engines | local-management |

<a id="op-health_health_get"></a>

## GET `/health`

Health

范围：`business`。Operation ID：`health_health_get`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `object` | Successful Response |

<a id="op-version_version_get"></a>

## GET `/version`

Version

范围：`business`。Operation ID：`version_version_get`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `object` | Successful Response |

<a id="op-finalize_agent_identity_credentials_agent_identity_finalize_post"></a>

## POST `/agent-identity/finalize`

Finalize Agent Identity Credentials

范围：`conditional`。Operation ID：`finalize_agent_identity_credentials_agent_identity_finalize_post`。

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`FinalizeAgentIdentityCredentialsRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `connectorName` | 是 | `string` |  |
| `userId` | 是 | `string` |  |
| `userIdValidationState` | 是 | `string` |  |
| `consentNonce` | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `object` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_apps_list_apps_get"></a>

## GET `/list-apps`

List Apps

范围：`business`。Operation ID：`list_apps_list_apps_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `detailed` | query | 否 | `boolean` | 默认 false。Return detailed app information |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `string`[] / `ListAppsResponse` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_adk_app_info_apps__app_name__app_info_get"></a>

## GET `/apps/{app_name}/app-info`

Get Adk App Info

范围：`business`。Operation ID：`get_adk_app_info_apps__app_name__app_info_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `AppInfo` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_session_apps__app_name__users__user_id__sessions__session_id__get"></a>

## GET `/apps/{app_name}/users/{user_id}/sessions/{session_id}`

Get Session

范围：`business`。Operation ID：`get_session_apps__app_name__users__user_id__sessions__session_id__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `Session` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-create_session_with_id_apps__app_name__users__user_id__sessions__session_id__post"></a>

## POST `/apps/{app_name}/users/{user_id}/sessions/{session_id}`

Create Session With Id

范围：`business`。Operation ID：`create_session_with_id_apps__app_name__users__user_id__sessions__session_id__post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |

### 请求体

是否必填：否。

Content-Type：`application/json`。类型：`object` / `null`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `Session` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-delete_session_apps__app_name__users__user_id__sessions__session_id__delete"></a>

## DELETE `/apps/{app_name}/users/{user_id}/sessions/{session_id}`

Delete Session

范围：`business`。Operation ID：`delete_session_apps__app_name__users__user_id__sessions__session_id__delete`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-update_session_apps__app_name__users__user_id__sessions__session_id__patch"></a>

## PATCH `/apps/{app_name}/users/{user_id}/sessions/{session_id}`

Update Session

范围：`business`。Operation ID：`update_session_apps__app_name__users__user_id__sessions__session_id__patch`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`UpdateSessionRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `stateDelta` | 是 | `object` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `Session` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_sessions_apps__app_name__users__user_id__sessions_get"></a>

## GET `/apps/{app_name}/users/{user_id}/sessions`

List Sessions

范围：`business`。Operation ID：`list_sessions_apps__app_name__users__user_id__sessions_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `Session`[] | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-create_session_apps__app_name__users__user_id__sessions_post"></a>

## POST `/apps/{app_name}/users/{user_id}/sessions`

Create Session

范围：`business`。Operation ID：`create_session_apps__app_name__users__user_id__sessions_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |

### 请求体

是否必填：否。

Content-Type：`application/json`。类型：`CreateSessionRequest` / `null`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `sessionId` | 否 | `string` / `null` | The ID of the session to create. If not provided, a random session ID will be generated. |
| `state` | 否 | `object` / `null` | The initial state of the session. |
| `events` | 否 | `Event-Input`[] / `null` | A list of events to initialize the session with. |
| `options` | 否 | `object` / `null` | Optional configuration options forwarded to the session service. |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `Session` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_artifact_version_metadata_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions__version_id__metadata_get"></a>

## GET `/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}/versions/{version_id}/metadata`

Get Artifact Version Metadata

范围：`business`。Operation ID：`get_artifact_version_metadata_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions__version_id__metadata_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |
| `artifact_name` | path | 是 | `string` |  |
| `version_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ArtifactVersion` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_artifact_versions_metadata_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions_metadata_get"></a>

## GET `/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}/versions/metadata`

List Artifact Versions Metadata

范围：`business`。Operation ID：`list_artifact_versions_metadata_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions_metadata_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |
| `artifact_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ArtifactVersion`[] | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-save_artifact_apps__app_name__users__user_id__sessions__session_id__artifacts_post"></a>

## POST `/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts`

Save Artifact

范围：`business`。Operation ID：`save_artifact_apps__app_name__users__user_id__sessions__session_id__artifacts_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`SaveArtifactRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `filename` | 是 | `string` | Artifact filename. |
| `artifact` | 是 | `Part` | Artifact payload encoded as google.genai.types.Part. |
| `customMetadata` | 否 | `object` / `null` | Optional metadata to associate with the artifact version. |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ArtifactVersion` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_artifact_names_apps__app_name__users__user_id__sessions__session_id__artifacts_get"></a>

## GET `/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts`

List Artifact Names

范围：`business`。Operation ID：`list_artifact_names_apps__app_name__users__user_id__sessions__session_id__artifacts_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `string`[] | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-load_artifact_version_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions__version_id__get"></a>

## GET `/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}/versions/{version_id}`

Load Artifact Version

范围：`business`。Operation ID：`load_artifact_version_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions__version_id__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |
| `artifact_name` | path | 是 | `string` |  |
| `version_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `Part` / `null` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_artifact_versions_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions_get"></a>

## GET `/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}/versions`

List Artifact Versions

范围：`business`。Operation ID：`list_artifact_versions_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__versions_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |
| `artifact_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `integer`[] | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-load_artifact_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__get"></a>

## GET `/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}`

Load Artifact

范围：`business`。Operation ID：`load_artifact_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |
| `artifact_name` | path | 是 | `string` |  |
| `version` | query | 否 | `integer` / `null` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `Part` / `null` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-delete_artifact_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__delete"></a>

## DELETE `/apps/{app_name}/users/{user_id}/sessions/{session_id}/artifacts/{artifact_name}`

Delete Artifact

范围：`business`。Operation ID：`delete_artifact_apps__app_name__users__user_id__sessions__session_id__artifacts__artifact_name__delete`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |
| `artifact_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-patch_memory_apps__app_name__users__user_id__memory_patch"></a>

## PATCH `/apps/{app_name}/users/{user_id}/memory`

Patch Memory

范围：`conditional`。Operation ID：`patch_memory_apps__app_name__users__user_id__memory_patch`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`UpdateMemoryRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `sessionId` | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-run_agent_run_post"></a>

## POST `/run`

Run Agent

范围：`business`。Operation ID：`run_agent_run_post`。

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`RunAgentRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `appName` | 否 | `string` / `null` |  |
| `userId` | 是 | `string` |  |
| `sessionId` | 是 | `string` |  |
| `newMessage` | 否 | `Content` / `null` |  |
| `streaming` | 否 | `boolean` | 默认 false。 |
| `stateDelta` | 否 | `object` / `null` |  |
| `functionCallEventId` | 否 | `string` / `null` |  |
| `invocationId` | 否 | `string` / `null` |  |
| `customMetadata` | 否 | `object` / `null` |  |
| `serviceTier` | 否 | `ServiceTier` / `string` / `null` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `Event-Output`[] | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 应用参数、访问来源或会话检查失败 |
| 403 | `application/json` | `ProjectError` | 应用参数、访问来源或会话检查失败 |
| 403 | `text/plain` | `string` | 应用参数、访问来源或会话检查失败 |
| 404 | `application/json` | `ProjectError` | 应用参数、访问来源或会话检查失败 |

<a id="op-run_agent_sse_run_sse_post"></a>

## POST `/run_sse`

Run Agent Sse

范围：`business`。Operation ID：`run_agent_sse_run_sse_post`。

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`RunAgentRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `appName` | 否 | `string` / `null` |  |
| `userId` | 是 | `string` |  |
| `sessionId` | 是 | `string` |  |
| `newMessage` | 否 | `Content` / `null` |  |
| `streaming` | 否 | `boolean` | 默认 false。 |
| `stateDelta` | 否 | `object` / `null` |  |
| `functionCallEventId` | 否 | `string` / `null` |  |
| `invocationId` | 否 | `string` / `null` |  |
| `customMetadata` | 否 | `object` / `null` |  |
| `serviceTier` | 否 | `ServiceTier` / `string` / `null` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `text/event-stream` | `string` | SSE 流；每个 data 帧为 Event 或流内错误 JSON，结束时关闭连接，无 [DONE] 帧。 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 应用参数、访问来源或会话检查失败 |
| 403 | `application/json` | `ProjectError` | 应用参数、访问来源或会话检查失败 |
| 403 | `text/plain` | `string` | 应用参数、访问来源或会话检查失败 |
| 404 | `application/json` | `ProjectError` | 应用参数、访问来源或会话检查失败 |

<a id="op-get_runtime_config_dev_ui_assets_config_runtime_config_json_get"></a>

## GET `/dev-ui/assets/config/runtime-config.json`

Get Runtime Config

范围：`development`。Operation ID：`get_runtime_config_dev_ui_assets_config_runtime_config_json_get`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |

<a id="op-get_ui_config_dev_ui_config_get"></a>

## GET `/dev-ui/config`

Get Ui Config

范围：`development`。Operation ID：`get_ui_config_dev_ui_config_get`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |

<a id="op-redirect_root_to_dev_ui__get"></a>

## GET `/`

Redirect Root To Dev Ui

范围：`development`。Operation ID：`redirect_root_to_dev_ui__get`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |

<a id="op-redirect_dev_ui_add_slash_dev_ui_get"></a>

## GET `/dev-ui`

Redirect Dev Ui Add Slash

范围：`development`。Operation ID：`redirect_dev_ui_add_slash_dev_ui_get`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |

<a id="op-get_telemetry_consent_config_telemetry_get"></a>

## GET `/config/telemetry`

Get Telemetry Consent

范围：`development`。Operation ID：`get_telemetry_consent_config_telemetry_get`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `object` | Successful Response |

<a id="op-set_telemetry_consent_config_telemetry_post"></a>

## POST `/config/telemetry`

Set Telemetry Consent

范围：`development`。Operation ID：`set_telemetry_consent_config_telemetry_post`。

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`TelemetryConsentRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `telemetry` | 是 | `boolean` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `object` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-builder_build_dev_apps__app_name__builder_save_post"></a>

## POST `/dev/apps/{app_name}/builder/save`

Builder Build

范围：`development`。Operation ID：`builder_build_dev_apps__app_name__builder_save_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `tmp` | query | 否 | `boolean` / `null` | 默认 false。 |

### 请求体

是否必填：是。

Content-Type：`multipart/form-data`。类型：`Body_builder_build_dev_apps__app_name__builder_save_post`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `files` | 是 | `string`[] |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `boolean` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-builder_cancel_dev_apps__app_name__builder_cancel_post"></a>

## POST `/dev/apps/{app_name}/builder/cancel`

Builder Cancel

范围：`development`。Operation ID：`builder_cancel_dev_apps__app_name__builder_cancel_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `boolean` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_agent_builder_dev_apps__app_name__builder_get"></a>

## GET `/dev/apps/{app_name}/builder`

Get Agent Builder

范围：`development`。Operation ID：`get_agent_builder_dev_apps__app_name__builder_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `file_path` | query | 否 | `string` / `null` |  |
| `tmp` | query | 否 | `boolean` / `null` | 默认 false。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `text/plain` | `string` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_trace_dict_dev_apps__app_name__debug_trace__event_id__get"></a>

## GET `/dev/apps/{app_name}/debug/trace/{event_id}`

Get Trace Dict

范围：`development`。Operation ID：`get_trace_dict_dev_apps__app_name__debug_trace__event_id__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `event_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_session_trace_dev_apps__app_name__debug_trace_session__session_id__get"></a>

## GET `/dev/apps/{app_name}/debug/trace/session/{session_id}`

Get Session Trace

范围：`development`。Operation ID：`get_session_trace_dev_apps__app_name__debug_trace_session__session_id__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_app_info_dev_apps__app_name__build_graph_get"></a>

## GET `/dev/apps/{app_name}/build_graph`

Get App Info

范围：`development`。Operation ID：`get_app_info_dev_apps__app_name__build_graph_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_app_info_image_dev_apps__app_name__build_graph_image_get"></a>

## GET `/dev/apps/{app_name}/build_graph_image`

Get App Info Image

范围：`development`。Operation ID：`get_app_info_image_dev_apps__app_name__build_graph_image_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `dark_mode` | query | 否 | `boolean` | 默认 false。 |
| `node` | query | 否 | `string` / `null` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `object` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_tests_dev_apps__app_name__tests_get"></a>

## GET `/dev/apps/{app_name}/tests`

List Tests

范围：`development`。Operation ID：`list_tests_dev_apps__app_name__tests_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `string`[] | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-rebuild_app_tests_dev_apps__app_name__tests_rebuild_post"></a>

## POST `/dev/apps/{app_name}/tests/rebuild`

Rebuild App Tests

范围：`development`。Operation ID：`rebuild_app_tests_dev_apps__app_name__tests_rebuild_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `test_name` | query | 否 | `string` / `null` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `object` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-run_app_tests_dev_apps__app_name__tests_run_post"></a>

## POST `/dev/apps/{app_name}/tests/run`

Run App Tests

范围：`development`。Operation ID：`run_app_tests_dev_apps__app_name__tests_run_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `test_name` | query | 否 | `string` / `null` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-create_test_dev_apps__app_name__tests__test_name__put"></a>

## PUT `/dev/apps/{app_name}/tests/{test_name}`

Create Test

范围：`development`。Operation ID：`create_test_dev_apps__app_name__tests__test_name__put`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `test_name` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`CreateTestRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `sessionData` | 是 | `object` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `object` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-delete_test_dev_apps__app_name__tests__test_name__delete"></a>

## DELETE `/dev/apps/{app_name}/tests/{test_name}`

Delete Test

范围：`development`。Operation ID：`delete_test_dev_apps__app_name__tests__test_name__delete`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `test_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `object` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_test_content_dev_apps__app_name__tests__test_name__get"></a>

## GET `/dev/apps/{app_name}/tests/{test_name}`

Get Test Content

范围：`development`。Operation ID：`get_test_content_dev_apps__app_name__tests__test_name__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `test_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `object` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-create_eval_set_dev_apps__app_name__eval_sets_post"></a>

## POST `/dev/apps/{app_name}/eval-sets`

Create Eval Set

范围：`development`。Operation ID：`create_eval_set_dev_apps__app_name__eval_sets_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`CreateEvalSetRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `evalSet` | 是 | `EvalSet` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `EvalSet` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_eval_sets_dev_apps__app_name__eval_sets_get"></a>

## GET `/dev/apps/{app_name}/eval-sets`

List Eval Sets

范围：`development`。Operation ID：`list_eval_sets_dev_apps__app_name__eval_sets_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ListEvalSetsResponse` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-create_eval_set_legacy_dev_apps__app_name__eval_sets__eval_set_id__post"></a>

## POST `/dev/apps/{app_name}/eval_sets/{eval_set_id}`

Create Eval Set Legacy

范围：`development`。Operation ID：`create_eval_set_legacy_dev_apps__app_name__eval_sets__eval_set_id__post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_eval_sets_legacy_dev_apps__app_name__eval_sets_get"></a>

## GET `/dev/apps/{app_name}/eval_sets`

List Eval Sets Legacy

范围：`development`。Operation ID：`list_eval_sets_legacy_dev_apps__app_name__eval_sets_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `string`[] | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-run_eval_legacy_dev_apps__app_name__eval_sets__eval_set_id__run_eval_post"></a>

## POST `/dev/apps/{app_name}/eval_sets/{eval_set_id}/run_eval`

Run Eval Legacy

范围：`development`。Operation ID：`run_eval_legacy_dev_apps__app_name__eval_sets__eval_set_id__run_eval_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`RunEvalRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `evalIds` | 否 | `string`[] | This field is deprecated, use eval_case_ids instead. |
| `evalCaseIds` | 否 | `string`[] | List of eval case ids to evaluate. if empty, then all eval cases in the eval set are run. |
| `evalMetrics` | 是 | `EvalMetric`[] |  |
| `liveModelConfig` | 否 | `LiveModelConfig` / `null` | Config for running inference in live (bidirectional streaming) mode. Required for Live API models (e.g. `gemini-*-live-*`). |
| `userSimulatorConfig` | 否 | `object` / `null` | Optional user-simulator configuration. The concrete type is selected via the `type` discriminator (e.g. `{"type": "llm_audio", ...}`). |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `RunEvalResult`[] | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_eval_result_legacy_dev_apps__app_name__eval_results__eval_result_id__get"></a>

## GET `/dev/apps/{app_name}/eval_results/{eval_result_id}`

Get Eval Result Legacy

范围：`development`。Operation ID：`get_eval_result_legacy_dev_apps__app_name__eval_results__eval_result_id__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_result_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `EvalSetResult` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_eval_results_legacy_dev_apps__app_name__eval_results_get"></a>

## GET `/dev/apps/{app_name}/eval_results`

List Eval Results Legacy

范围：`development`。Operation ID：`list_eval_results_legacy_dev_apps__app_name__eval_results_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `string`[] | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-add_session_to_eval_set_dev_apps__app_name__eval_sets__eval_set_id__add_session_post__c786ed2b"></a>

## POST `/dev/apps/{app_name}/eval_sets/{eval_set_id}/add_session`

Add Session To Eval Set

范围：`development`。Operation ID：`add_session_to_eval_set_dev_apps__app_name__eval_sets__eval_set_id__add_session_post__c786ed2b`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`AddSessionToEvalSetRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `evalId` | 是 | `string` |  |
| `sessionId` | 是 | `string` |  |
| `userId` | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-add_session_to_eval_set_dev_apps__app_name__eval_sets__eval_set_id__add_session_post__5c8b5092"></a>

## POST `/dev/apps/{app_name}/eval-sets/{eval_set_id}/add-session`

Add Session To Eval Set

范围：`development`。Operation ID：`add_session_to_eval_set_dev_apps__app_name__eval_sets__eval_set_id__add_session_post__5c8b5092`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`AddSessionToEvalSetRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `evalId` | 是 | `string` |  |
| `sessionId` | 是 | `string` |  |
| `userId` | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_evals_in_eval_set_dev_apps__app_name__eval_sets__eval_set_id__evals_get"></a>

## GET `/dev/apps/{app_name}/eval_sets/{eval_set_id}/evals`

List Evals In Eval Set

范围：`development`。Operation ID：`list_evals_in_eval_set_dev_apps__app_name__eval_sets__eval_set_id__evals_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `string`[] | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_eval_dev_apps__app_name__eval_sets__eval_set_id__evals__eval_case_id__get"></a>

## GET `/dev/apps/{app_name}/eval_sets/{eval_set_id}/evals/{eval_case_id}`

Get Eval

范围：`development`。Operation ID：`get_eval_dev_apps__app_name__eval_sets__eval_set_id__evals__eval_case_id__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |
| `eval_case_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `EvalCase` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-update_eval_dev_apps__app_name__eval_sets__eval_set_id__evals__eval_case_id__put"></a>

## PUT `/dev/apps/{app_name}/eval_sets/{eval_set_id}/evals/{eval_case_id}`

Update Eval

范围：`development`。Operation ID：`update_eval_dev_apps__app_name__eval_sets__eval_set_id__evals__eval_case_id__put`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |
| `eval_case_id` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`EvalCase`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `evalId` | 是 | `string` |  |
| `conversation` | 否 | `Invocation`[] / `null` |  |
| `conversationScenario` | 否 | `ConversationScenario` / `null` |  |
| `sessionInput` | 否 | `SessionInput` / `null` |  |
| `creationTimestamp` | 否 | `number` | 默认 0.0。 |
| `rubrics` | 否 | `Rubric`[] / `null` |  |
| `finalSessionState` | 否 | `object` / `null` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-delete_eval_dev_apps__app_name__eval_sets__eval_set_id__evals__eval_case_id__delete"></a>

## DELETE `/dev/apps/{app_name}/eval_sets/{eval_set_id}/evals/{eval_case_id}`

Delete Eval

范围：`development`。Operation ID：`delete_eval_dev_apps__app_name__eval_sets__eval_set_id__evals__eval_case_id__delete`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |
| `eval_case_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_eval_dev_apps__app_name__eval_sets__eval_set_id__eval_cases__eval_case_id__get"></a>

## GET `/dev/apps/{app_name}/eval-sets/{eval_set_id}/eval-cases/{eval_case_id}`

Get Eval

范围：`development`。Operation ID：`get_eval_dev_apps__app_name__eval_sets__eval_set_id__eval_cases__eval_case_id__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |
| `eval_case_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `EvalCase` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-update_eval_dev_apps__app_name__eval_sets__eval_set_id__eval_cases__eval_case_id__put"></a>

## PUT `/dev/apps/{app_name}/eval-sets/{eval_set_id}/eval-cases/{eval_case_id}`

Update Eval

范围：`development`。Operation ID：`update_eval_dev_apps__app_name__eval_sets__eval_set_id__eval_cases__eval_case_id__put`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |
| `eval_case_id` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`EvalCase`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `evalId` | 是 | `string` |  |
| `conversation` | 否 | `Invocation`[] / `null` |  |
| `conversationScenario` | 否 | `ConversationScenario` / `null` |  |
| `sessionInput` | 否 | `SessionInput` / `null` |  |
| `creationTimestamp` | 否 | `number` | 默认 0.0。 |
| `rubrics` | 否 | `Rubric`[] / `null` |  |
| `finalSessionState` | 否 | `object` / `null` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-delete_eval_dev_apps__app_name__eval_sets__eval_set_id__eval_cases__eval_case_id__delete"></a>

## DELETE `/dev/apps/{app_name}/eval-sets/{eval_set_id}/eval-cases/{eval_case_id}`

Delete Eval

范围：`development`。Operation ID：`delete_eval_dev_apps__app_name__eval_sets__eval_set_id__eval_cases__eval_case_id__delete`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |
| `eval_case_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-run_eval_dev_apps__app_name__eval_sets__eval_set_id__run_post"></a>

## POST `/dev/apps/{app_name}/eval-sets/{eval_set_id}/run`

Run Eval

范围：`development`。Operation ID：`run_eval_dev_apps__app_name__eval_sets__eval_set_id__run_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_set_id` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`RunEvalRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `evalIds` | 否 | `string`[] | This field is deprecated, use eval_case_ids instead. |
| `evalCaseIds` | 否 | `string`[] | List of eval case ids to evaluate. if empty, then all eval cases in the eval set are run. |
| `evalMetrics` | 是 | `EvalMetric`[] |  |
| `liveModelConfig` | 否 | `LiveModelConfig` / `null` | Config for running inference in live (bidirectional streaming) mode. Required for Live API models (e.g. `gemini-*-live-*`). |
| `userSimulatorConfig` | 否 | `object` / `null` | Optional user-simulator configuration. The concrete type is selected via the `type` discriminator (e.g. `{"type": "llm_audio", ...}`). |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `RunEvalResponse` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_eval_result_dev_apps__app_name__eval_results__eval_result_id__get"></a>

## GET `/dev/apps/{app_name}/eval-results/{eval_result_id}`

Get Eval Result

范围：`development`。Operation ID：`get_eval_result_dev_apps__app_name__eval_results__eval_result_id__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `eval_result_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `EvalResult` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_eval_results_dev_apps__app_name__eval_results_get"></a>

## GET `/dev/apps/{app_name}/eval-results`

List Eval Results

范围：`development`。Operation ID：`list_eval_results_dev_apps__app_name__eval_results_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ListEvalResultsResponse` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-list_metrics_info_dev_apps__app_name__metrics_info_get"></a>

## GET `/dev/apps/{app_name}/metrics-info`

List Metrics Info

范围：`development`。Operation ID：`list_metrics_info_dev_apps__app_name__metrics_info_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ListMetricsInfoResponse` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_app_graph_dot_dev_apps__app_name__graph_get"></a>

## GET `/dev/apps/{app_name}/graph`

Get App Graph Dot

范围：`development`。Operation ID：`get_app_graph_dot_dev_apps__app_name__graph_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `dark_mode` | query | 否 | `boolean` | 默认 false。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `GetEventGraphResult` / `object` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_event_graph_dev_apps__app_name__users__user_id__sessions__session_id__events__event_id__graph_get"></a>

## GET `/dev/apps/{app_name}/users/{user_id}/sessions/{session_id}/events/{event_id}/graph`

Get Event Graph

范围：`development`。Operation ID：`get_event_graph_dev_apps__app_name__users__user_id__sessions__session_id__events__event_id__graph_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |
| `user_id` | path | 是 | `string` |  |
| `session_id` | path | 是 | `string` |  |
| `event_id` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `any` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-get_deploy_defaults_dev_apps__app_name__deploy_defaults_get"></a>

## GET `/dev/apps/{app_name}/deploy/defaults`

Get Deploy Defaults

范围：`conditional`。Operation ID：`get_deploy_defaults_dev_apps__app_name__deploy_defaults_get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `DeployDefaults` | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-deploy_to_agent_engine_dev_apps__app_name__deploy_agent_engine_post"></a>

## POST `/dev/apps/{app_name}/deploy/agent_engine`

Deploy To Agent Engine

范围：`conditional`。Operation ID：`deploy_to_agent_engine_dev_apps__app_name__deploy_agent_engine_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`AgentEngineDeployRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `region` | 是 | `string` |  |
| `project` | 否 | `string` / `null` |  |
| `displayName` | 否 | `string` / `null` |  |
| `description` | 否 | `string` / `null` |  |
| `agentEngineId` | 否 | `string` / `null` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | — | — | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-deploy_to_cloud_run_dev_apps__app_name__deploy_cloud_run_post"></a>

## POST `/dev/apps/{app_name}/deploy/cloud_run`

Deploy To Cloud Run

范围：`conditional`。Operation ID：`deploy_to_cloud_run_dev_apps__app_name__deploy_cloud_run_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`CloudRunDeployRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `region` | 是 | `string` |  |
| `project` | 否 | `string` / `null` |  |
| `serviceName` | 是 | `string` |  |
| `port` | 否 | `integer` | 默认 8000。 |
| `withUi` | 否 | `boolean` | 默认 false。 |
| `allowUnauthenticated` | 否 | `boolean` | 默认 false。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | — | — | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-deploy_to_gke_dev_apps__app_name__deploy_gke_post"></a>

## POST `/dev/apps/{app_name}/deploy/gke`

Deploy To Gke

范围：`conditional`。Operation ID：`deploy_to_gke_dev_apps__app_name__deploy_gke_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `app_name` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`GkeDeployRequest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `region` | 是 | `string` |  |
| `project` | 否 | `string` / `null` |  |
| `serviceName` | 是 | `string` |  |
| `port` | 否 | `integer` | 默认 8000。 |
| `withUi` | 否 | `boolean` | 默认 false。 |
| `clusterName` | 是 | `string` |  |
| `serviceType` | 否 | `ClusterIP` / `LoadBalancer` | 默认 "ClusterIP"。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | — | — | Successful Response |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |

<a id="op-state_capabilities_api_state_get"></a>

## GET `/capabilities/api/state`

读取 MCP、Skill 与应用绑定状态

范围：`local-management`。Operation ID：`state_capabilities_api_state_get`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectCapabilityState` | 操作完成；具体含义见接口说明 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-save_server_capabilities_api_mcp__sid__put"></a>

## PUT `/capabilities/api/mcp/{sid}`

保存 MCP 服务，不自动连接或绑定

范围：`local-management`。Operation ID：`save_server_capabilities_api_mcp__sid__put`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `sid` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`ProjectMcpSave`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `revision` | 是 | `string` | 从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。 |
| `server` | 是 | `ProjectMcpServerInput` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectCapabilityState` | 操作完成；具体含义见接口说明 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-test_server_capabilities_api_mcp__sid__test_post"></a>

## POST `/capabilities/api/mcp/{sid}/test`

连接已保存 MCP 服务并发布发现的工具

范围：`local-management`。Operation ID：`test_server_capabilities_api_mcp__sid__test_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `sid` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`ProjectRevisionBody`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `revision` | 是 | `string` | 从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectCapabilityState` | 操作完成；具体含义见接口说明 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 404 | `application/json` | `ProjectError` | 资源或引擎不存在 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |
| 502 | `application/json` | `ProjectError` | 上游连接/推理失败 |

<a id="op-remove_capabilities_api__kind___identifier__delete"></a>

## DELETE `/capabilities/api/{kind}/{identifier}`

移出 MCP 服务或 Skill；被绑定时拒绝

范围：`local-management`。Operation ID：`remove_capabilities_api__kind___identifier__delete`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `kind` | path | 是 | `mcp` / `skills` |  |
| `identifier` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`ProjectRevisionBody`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `revision` | 是 | `string` | 从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectCapabilityState` | 操作完成；具体含义见接口说明 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 404 | `application/json` | `ProjectError` | 资源或引擎不存在 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-import_skill_capabilities_api_skills_import_post"></a>

## POST `/capabilities/api/skills/import`

导入单个 Skill ZIP / .skill 包

范围：`local-management`。Operation ID：`import_skill_capabilities_api_skills_import_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `revision` | query | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/zip`。类型：`string (binary)`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectCapabilityState` | 操作完成；具体含义见接口说明 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-create_skill_capabilities_api_skills_post"></a>

## POST `/capabilities/api/skills`

新建 Skill，不自动绑定应用

范围：`local-management`。Operation ID：`create_skill_capabilities_api_skills_post`。

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`ProjectSkillSave`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `revision` | 是 | `string` | 从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。 |
| `files` | 是 | `object` |  |
| `enabled` | 否 | `boolean` | 默认 true。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectCapabilityState` | 操作完成；具体含义见接口说明 |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-read_skill_capabilities_api_skills__sid__get"></a>

## GET `/capabilities/api/skills/{sid}`

读取 Skill 文件及版本目录

范围：`local-management`。Operation ID：`read_skill_capabilities_api_skills__sid__get`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `sid` | path | 是 | `string` |  |
| `version` | query | 否 | `integer` / `null` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectSkillRead` | 操作完成；具体含义见接口说明 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 404 | `application/json` | `ProjectError` | 资源或引擎不存在 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-update_skill_capabilities_api_skills__sid__put"></a>

## PUT `/capabilities/api/skills/{sid}`

编辑 Skill，发布新的不可变版本

范围：`local-management`。Operation ID：`update_skill_capabilities_api_skills__sid__put`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `sid` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`ProjectSkillSave`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `revision` | 是 | `string` | 从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。 |
| `files` | 是 | `object` |  |
| `enabled` | 否 | `boolean` | 默认 true。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectCapabilityState` | 操作完成；具体含义见接口说明 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 404 | `application/json` | `ProjectError` | 资源或引擎不存在 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-restore_skill_capabilities_api_skills__sid__restore__version__post"></a>

## POST `/capabilities/api/skills/{sid}/restore/{version}`

将历史内容恢复为新的 Skill 版本

范围：`local-management`。Operation ID：`restore_skill_capabilities_api_skills__sid__restore__version__post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `sid` | path | 是 | `string` |  |
| `version` | path | 是 | `integer` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`ProjectRevisionBody`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `revision` | 是 | `string` | 从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectCapabilityState` | 操作完成；具体含义见接口说明 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 404 | `application/json` | `ProjectError` | 资源或引擎不存在 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-bind_agent_capabilities_api_agents__agent_name__put"></a>

## PUT `/capabilities/api/agents/{agent_name}`

按应用保存 MCP 工具白名单与 Skill 绑定

范围：`local-management`。Operation ID：`bind_agent_capabilities_api_agents__agent_name__put`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `agent_name` | path | 是 | `string` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`ProjectBindingSave`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `revision` | 是 | `string` | 从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。 |
| `binding` | 是 | `ProjectAgentBinding` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectCapabilityState` | 操作完成；具体含义见接口说明 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 404 | `application/json` | `ProjectError` | 资源或引擎不存在 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-state_capabilities_api_models_get"></a>

## GET `/capabilities/api/models`

读取模型引擎状态，不返回已保存 Key

范围：`local-management`。Operation ID：`state_capabilities_api_models_get`。

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectModelState` | 操作完成；具体含义见接口说明 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-default_capabilities_api_models_default_put"></a>

## PUT `/capabilities/api/models/default`

设置新 Agent 默认模型

范围：`local-management`。Operation ID：`default_capabilities_api_models_default_put`。

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`ProjectDefaultModel`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `revision` | 是 | `string` | 从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。 |
| `reference` | 是 | `string` |  |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectModelState` | 操作完成；具体含义见接口说明 |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-save_capabilities_api_models__engine__put"></a>

## PUT `/capabilities/api/models/{engine}`

保存引擎连接及本机 Key

范围：`local-management`。Operation ID：`save_capabilities_api_models__engine__put`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `engine` | path | 是 | `deepseek` / `kimi` / `openai` / `claude` / `openrouter` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`ProjectEngineSave`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `revision` | 是 | `string` | 从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。 |
| `settings` | 是 | `ProjectEngineSettings` |  |
| `api_key` | 否 | `string` / `null` | 空白或省略保留原 Key；不能含空白字符。 |
| `clear_key` | 否 | `boolean` | 默认 false。仅清除本机保存值；环境变量仍可提供 Key。不能与非空 api_key 同时提交。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectModelState` | 操作完成；具体含义见接口说明 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 404 | `application/json` | `ProjectError` | 资源或引擎不存在 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |

<a id="op-test_capabilities_api_models__engine__test_post"></a>

## POST `/capabilities/api/models/{engine}/test`

测试当前表单或读取模型列表，不保存

范围：`local-management`。Operation ID：`test_capabilities_api_models__engine__test_post`。

### 路径与查询参数

| 参数 | 位置 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- | --- |
| `engine` | path | 是 | `deepseek` / `kimi` / `openai` / `claude` / `openrouter` |  |

### 请求体

是否必填：是。

Content-Type：`application/json`。类型：`ProjectEngineTest`。

| 字段 | 必填 | 类型 | 默认值 / 说明 |
| --- | --- | --- | --- |
| `revision` | 是 | `string` | 从对应 GET 状态接口读取的 revision；模型与能力配置使用不同版本。 |
| `settings` | 是 | `ProjectEngineSettings` |  |
| `api_key` | 否 | `string` / `null` | 空白或省略保留原 Key；不能含空白字符。 |
| `clear_key` | 否 | `boolean` | 默认 false。仅清除本机保存值；环境变量仍可提供 Key。不能与非空 api_key 同时提交。 |
| `purpose` | 否 | `inference` / `models` | 默认 "inference"。inference 实际发送简短消息；models 仅读模型目录。均不保存配置。 |

### 响应

| HTTP 状态 | Content-Type | 类型 | 说明 |
| --- | --- | --- | --- |
| 200 | `application/json` | `ProjectProbeInference` / `ProjectProbeModels` | 操作完成；具体含义见接口说明 |
| 422 | `application/json` | `HTTPValidationError` | Validation Error |
| 400 | `application/json` | `ProjectError` | 业务参数或资源约束不满足 |
| 403 | `application/json` | `ProjectError` | 本机同源访问检查失败 |
| 404 | `application/json` | `ProjectError` | 资源或引擎不存在 |
| 409 | `application/json` | `ProjectError` | 版本冲突或资源已存在 |
| 413 | `application/json` | `ProjectError` | 请求过大 |
| 415 | `application/json` | `ProjectError` | Content-Type 不支持 |
| 500 | `application/json` | `ProjectError` | 本机配置或存储错误 |
| 502 | `application/json` | `ProjectError` | 上游连接/推理失败 |
