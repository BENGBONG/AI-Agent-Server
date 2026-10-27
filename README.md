# AI-Agent-Server

基于 Google ADK 与 DeepSeek 的信用管家项目，包含 Agent 编辑与对话、公共工具、文件解析，以及按应用配置的 MCP / Skill 能力管理。

## 环境与启动

使用 Python 3.12。依赖版本固定在 `requirements.txt`，主要框架为 Google ADK 2.12.0 与 LiteLLM 1.106.1。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python configure_deepseek_key.py
python adk_web.py
```

打开 <http://127.0.0.1:8000>，选择 `credit_manager` 开始对话。密钥由根目录 `.env` 或 `DEEPSEEK_API_KEY` 环境变量提供；模型与接口地址在 `model_profiles.json` 配置。

当前服务监听本机 `127.0.0.1:8000`，未实现面向公网的应用认证和多租户管理。模型推理、联网搜索与可选图片识别通过 DeepSeek API 完成。

## 项目结构

| 路径 | 职责 |
| --- | --- |
| `adk_web.py` | 原生 ADK Web 启动、草稿加载、能力管理与附件插件接入 |
| `builder_models.py` / `builder_tools.py` | Builder 模型选项、生成配置往返与公共工具入口适配 |
| `model_runtime.py` / `model_profiles.json` | 模型注册、请求参数合并、默认模型与思考模式 |
| `credit_manager/` | 正式信用管家 YAML 和工具兼容入口 |
| `prompts/credit_manager_system_prompt_v2.txt` | 当前信用管家提示词来源 |
| `shared_tools/` | 公共工具注册、时间、网页搜索/读取、文档解析与图片识别 |
| `capabilities/` | MCP 服务配置、Skill 包管理、运行绑定、脚本执行及管理页源码 |
| `upload_handling.py` | 当前会话上传附件接入 |
| `test_*.py` | 回归测试，使用临时目录和合成资料 |
| `docs/` | 信用管家 Skill 体系、详细设计和业务规则填写稿 |

`shared_tools/registry.py` 是普通工具的唯一注册表。应用内 `tool_entries.py` 和 `deepseek_web_tools.py` 由 `builder_tools.py` 生成；新增工具应修改公共实现及注册表。

## 模型和能力配置

在原生 Agent 编辑页选择模型，按节点设置思考模式，使用原生 **Save / Cancel** 保存或放弃修改。思考模式写入 YAML 的 `generate_content_config.http_options.extra_body.thinking.type`；未配置时沿用模型 profile 默认值。根 Agent 与子 Agent 可分别配置。

MCP / Skill 面板集成在 ADK 当前页，也可通过 `/capabilities` 打开。能力面板单独保存，原生 Agent 的 **Save** 不会提交尚未保存的能力选择。绑定粒度为应用，同一应用的根 Agent 和子 Agent 使用该应用的能力绑定；每次 invocation 固定能力快照。

首次保存配置时创建 `capability_config.json`，导入的 Skill 版本保存在 `capabilities/skill_library/`。这些运行配置和包库在本机生成，不随仓库发布。MCP 支持远程 HTTP / SSE 及环境变量凭据引用，当前没有 stdio 或 OAuth 配置向导。

Skill 支持完整 ZIP / `.skill` 包、文本和二进制资源，以及原生 `run_skill_script`。脚本执行后端：macOS 使用 `sandbox-exec`；Linux 默认使用 Docker，镜像定义见 `capabilities/script_runtime/Dockerfile`。macOS 后端曾完成实际验收，Docker 后端仍需在部署机验证；不会自动安装包内依赖。

## 文件解析

公共工具支持当前会话中的 TXT / Markdown / CSV、DOCX、XLSX、PDF 和常见图片。PDF 优先本地提取，扫描页及图片可选择 DeepSeek 识别。工具限制可读范围为当前会话附件，不接受任意主机文件路径。需要确认、授权或资料核对的业务交互使用 `get_user_choice`；提示词本身不替代服务层授权。

## 业务设计状态

[Skill 体系设计](docs/credit-manager-skills-design-v1.md)和[逐项设计入口](docs/credit-skills-detailed-design-v1/README.md)覆盖 9 类业务与 3 类公共 Skill，含 89 项待填写规则。

这些文件是设计草案，尚未导入或绑定为运行能力；文档结构检查通过不代表业务功能已经实现。新增业务实现前，先确认对应规则、工具依赖和验收条件。

## 验证

现有回归不调用真实模型 API：

```bash
python -m unittest test_skill_packages test_capabilities test_file_tools test_tool_registry test_web_tools test_adk_web test_model_thinking -q
```

可选真实模型验收：

```bash
python validate_capabilities.py
python validate_model_thinking.py
```

真实模型验收使用临时 Agent 和合成数据，会调用 DeepSeek API；结果输出为本地 `validation_*.json`。这些脚本不代表全部业务场景或部署环境已经验收。

仓库仅收录项目源码、正式 Agent 配置、依赖、测试和相关业务设计。本机密钥、会话与附件、虚拟环境、入门示例、演示 Agent、编辑草稿和历史发布快照由 `.gitignore` 排除。
