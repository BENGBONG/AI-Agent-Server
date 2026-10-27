"use strict";
const API = "/capabilities/api";
const embedded = window.parent !== window && new URLSearchParams(location.search).get("embedded") === "1";
const requestedAgent = new URLSearchParams(location.search).get("app") || "";
if (embedded) document.body.classList.add("embedded");
let state, view = new URLSearchParams(location.search).get("view") === "models" ? "models" : "agents", selectedAgent, selectedServer = null, selectedSkill = null;
let skillFiles = {}, skillFile = "SKILL.md", skillVersions = [], viewedVersion = null;
let skillEnabled = true;
let dirty = false;
const content = document.getElementById("content"), notice = document.getElementById("notice");

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "list") node.setAttribute(key, value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) if (child !== null && child !== undefined) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return node;
}
function button(text, action, primary = false, extra = {}) { return el("button", {type:"button", class:"button" + (primary ? " primary" : ""), onclick:action, ...extra}, text); }
function field(label, input, help) { return el("div", {class:"field"}, el("label", {htmlFor:input.id}, label), input, help ? el("small", {}, help) : null); }
function input(id, value = "", extra = {}) { return el("input", {id, value, ...extra}); }
function select(id, values, value, onchange) {
  const node = el("select", {id, onchange});
  for (const [key, label] of values) node.append(el("option", {value:key}, label));
  node.value = value;
  return node;
}
function message(text, error = false) { notice.hidden = false; notice.className = error ? "error" : ""; notice.textContent = text; }
async function request(path, method = "GET", body) {
  const options = {method, headers:{}};
  if (body !== undefined) { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify({...body, revision:state.revision}); }
  const response = await fetch(API + path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "操作未完成，请检查输入后重试。");
  return result;
}
async function action(fn) {
  const buttons = [...content.querySelectorAll("button")].filter(x => !x.disabled);
  buttons.forEach(x => x.disabled = true);
  try { await fn(); } catch (error) { message(error.message, true); }
  finally { buttons.forEach(x => x.disabled = false); }
}
function changed() { dirty = true; }
function leaveDraft() { return !dirty || window.confirm("这里有未保存的内容，确定离开并放弃本次编辑吗？"); }
function switchView(next) {
  if (!leaveDraft()) return;
  if (dirty && view === "skills") { selectedSkill = null; skillFiles = {}; viewedVersion = null; skillEnabled = true; }
  view = next; dirty = false; notice.hidden = true; render();
}
function pageHead(label, title, subtitle, right) {
  return el("div", {class:"page-head"}, el("div", {}, el("div", {class:"heading-label"}, label), el("h1", {}, title), el("p", {class:"intro"}, subtitle)), right || null);
}
function badge(text, good = false) { return el("span", {class:"badge" + (good ? " good" : "")}, text); }
function empty(text, next, label) { return el("div", {class:"empty"}, el("div", {}, text), next ? button(label, next) : null); }
function check(title, description, checked, change, disabled = false) {
  return el("label", {class:"choice"}, el("input", {type:"checkbox", checked, disabled, onchange:event => { change(event.target.checked); changed(); }}), el("span", {}, el("strong", {}, title), el("small", {}, description)));
}
function render() {
  document.querySelectorAll(".nav-item").forEach(n => n.classList.toggle("active", n.dataset.view === view));
  content.replaceChildren();
  if (view === "agents") renderAgents();
  else if (view === "mcp") renderMcp();
  else if (view === "models") renderModels();
  else renderSkills();
}
function renderAgents() {
  if (embedded && requestedAgent && !state.agent_names.includes(requestedAgent)) {
    content.append(pageHead("CAPABILITY BINDINGS", "先保存新 Agent", "「" + requestedAgent + "」还没有被 ADK 识别。返回编辑并保存后，再打开能力配置。"));
    return;
  }
  if (!state.agent_names.includes(selectedAgent)) selectedAgent = state.agent_names.includes("credit_manager") ? "credit_manager" : state.agent_names[0];
  const binding = structuredClone(state.agents[selectedAgent] || {mcp:[], skills:[]});
  content.append(pageHead("CAPABILITY BINDINGS", "Agent 能力配置", "选择这个 Agent 可以使用的服务工具与技能。", el("div", {class:"stats"}, badge(Object.keys(state.mcp_servers).length + " 个服务"), badge(Object.keys(state.skills).length + " 个 Skill"))));
  const picker = select("agent-picker", state.agent_names.map(n => [n,n]), selectedAgent, event => { if (leaveDraft()) { selectedAgent = event.target.value; dirty = false; render(); } else event.target.value = selectedAgent; });
  picker.disabled = embedded && !!requestedAgent;
  const agentPanel = el("section", {class:"panel"}, field("当前 Agent", picker), el("p", {class:"help"}, "原有提示词、模型和普通工具继续在 ADK 编辑页维护；本页保存额外的能力绑定。"));
  if (selectedAgent && !embedded) agentPanel.append(el("a", {href:"/dev-ui/?app=" + encodeURIComponent(selectedAgent) + "&mode=builder"}, "打开这个 Agent 的编辑页 ↗"));
  content.append(agentPanel);
  const mcp = el("section", {class:"panel"}, el("div", {class:"section-head"}, el("h2", {}, "MCP 工具"), button("管理服务", () => switchView("mcp"))), el("p", {class:"help"}, "先登记并测试服务，再勾选具体工具。未选择的工具不会提供给这个 Agent。"));
  const servers = Object.values(state.mcp_servers);
  if (!servers.length) mcp.append(empty("还没有登记 MCP 服务", () => switchView("mcp"), "登记第一个服务"));
  for (const server of servers) {
    const block = el("div", {class:"mcp-block"}, el("div", {class:"row"}, el("h3", {}, server.name), badge(!server.enabled ? "已停用" : server.tested_at ? "连接已测试" : "待测试", server.enabled && server.tested_at)));
    block.append(el("div", {class:"help service-url"}, server.url));
    if (!server.tools.length) block.append(el("p", {class:"help"}, "在 MCP 服务页测试连接后，这里会显示可选工具。"));
    const tools = el("div", {class:"mcp-tools"});
    for (const tool of server.tools) {
      const item = binding.mcp.find(x => x.server_id === server.id);
      tools.append(check(tool.name, tool.description, !!item?.tools.includes(tool.name), on => {
        let entry = binding.mcp.find(x => x.server_id === server.id);
        if (on) { if (!entry) { entry = {server_id:server.id, tools:[]}; binding.mcp.push(entry); } entry.tools.push(tool.name); }
        else if (entry) { entry.tools = entry.tools.filter(x => x !== tool.name); if (!entry.tools.length) binding.mcp = binding.mcp.filter(x => x !== entry); }
      }, (!server.enabled || !server.tested_at) && !item?.tools.includes(tool.name)));
    }
    const entry = binding.mcp.find(x => x.server_id === server.id);
    for (const name of entry?.tools.filter(n => !server.tools.some(t => t.name === n)) || []) {
      tools.append(check(name + "（当前已不可用）", "服务更新后不再提供此工具，请取消选择再保存。", true, on => {
        if (!on) { entry.tools = entry.tools.filter(n => n !== name); if (!entry.tools.length) binding.mcp = binding.mcp.filter(x => x !== entry); }
      }));
    }
    block.append(tools); mcp.append(block);
  }
  content.append(mcp);
  const skills = el("section", {class:"panel"}, el("div", {class:"section-head"}, el("h2", {}, "Skills"), button("管理 Skill 库", () => switchView("skills"))), el("p", {class:"help"}, "技能按任务需要加载，提供流程指引与参考资料。它不会自动获得额外工具权限。"));
  if (!Object.keys(state.skills).length) skills.append(empty("还没有可用的 Skill", () => switchView("skills"), "创建或导入 Skill"));
  for (const skill of Object.values(state.skills)) skills.append(check(skill.id + " · v" + skill.version, skill.description + (!skill.enabled ? "（已停用）" : ""), binding.skills.includes(skill.id), on => { binding.skills = on ? [...binding.skills, skill.id] : binding.skills.filter(x => x !== skill.id); }, !skill.enabled && !binding.skills.includes(skill.id)));
  content.append(skills, el("div", {class:"selection-bar"}, el("div", {}, el("strong", {}, "保存后从下一次调用开始使用新配置"), el("small", {}, "已经运行中的调用保持原有选择；新建会话便于完整体验。")), button("保存 Agent 配置", () => action(async () => { state = await request("/agents/" + encodeURIComponent(selectedAgent), "PUT", {binding}); dirty = false; render(); message("已保存「" + selectedAgent + "」的能力选择。"); }), true, {disabled:!selectedAgent})));
}
function renderMcp() {
  content.append(pageHead("MCP CONNECTIONS", "MCP 服务", "统一登记连接，在 Agent 中选择需要的工具。", button("新增服务", () => { if (!leaveDraft()) return; selectedServer = null; dirty = false; render(); }, true)));
  const list = el("div", {});
  for (const server of Object.values(state.mcp_servers)) list.append(el("button", {class:"list-card" + (selectedServer === server.id ? " selected" : ""), onclick:() => { if (!leaveDraft()) return; selectedServer = server.id; dirty = false; render(); }}, el("strong", {}, server.name), el("small", {class:"service-url"}, server.url), badge(!server.enabled ? "已停用" : server.tested_at ? server.tools.length + " 个工具" : "待测试", server.enabled && server.tested_at)));
  if (!Object.keys(state.mcp_servers).length) list.append(empty("还没有服务。在右侧填写连接信息。"));
  const server = state.mcp_servers[selectedServer] || {id:"", name:"", transport:"streamable_http", url:"", token_env:"", auth_header:"Authorization", auth_prefix:"Bearer ", enabled:true, tools:[], tested_at:null};
  const id = input("server-id", server.id, {placeholder:"例如 institution-tools", disabled:!!selectedServer, required:true});
  const name = input("server-name", server.name, {placeholder:"例如 机构信息服务", required:true});
  const transport = select("server-transport", [["streamable_http","Streamable HTTP"],["sse","SSE"]], server.transport);
  const url = input("server-url", server.url, {placeholder:"https://your-service.example/mcp", type:"url", required:true});
  const token = input("server-token-env", server.token_env, {placeholder:"例如 INSTITUTION_MCP_TOKEN", autocomplete:"off"});
  const authHeader = input("server-auth-header", server.auth_header);
  const authPrefix = input("server-auth-prefix", server.auth_prefix);
  const enabled = el("input", {type:"checkbox", checked:server.enabled});
  const form = el("form", {class:"panel", oninput:changed}, el("h2", {}, selectedServer ? "编辑连接" : "登记服务"), el("p", {class:"help"}, "先保存，再测试连接以获取工具列表。此操作不自动为 Agent 启用工具。"), el("div", {class:"grid"}, field("服务 ID", id, "小写字母、数字和连字符；保存后不变。"), field("显示名称", name)), field("连接方式", transport), field("服务地址", url), field("凭据环境变量名（可选）", token, "这里填写变量名。实际密钥在服务器环境或项目 .env 中设置；无需在页面粘贴。"), el("div", {class:"grid"}, field("鉴权 Header", authHeader), field("值前缀", authPrefix, "Bearer 后通常保留一个空格；API Key 可留空。")), el("label", {class:"check-row"}, enabled, "允许 Agent 使用此服务"));
  const value = () => ({id:id.value.trim(), name:name.value.trim(), transport:transport.value, url:url.value.trim(), token_env:token.value.trim(), auth_header:authHeader.value.trim(), auth_prefix:authPrefix.value, enabled:enabled.checked});
  async function save() { const data = value(); state = await request("/mcp/" + encodeURIComponent(data.id), "PUT", {server:data}); selectedServer = data.id; dirty = false; }
  form.addEventListener("submit", event => { event.preventDefault(); action(async () => { await save(); render(); message("服务已保存，点击测试连接获取工具。"); }); });
  form.append(el("div", {class:"actions"}, el("button", {class:"button primary", type:"submit"}, "保存服务"), button("测试连接", () => action(async () => { if (!form.reportValidity()) return; message("正在连接服务并读取工具列表…"); await save(); state = await request("/mcp/" + encodeURIComponent(selectedServer) + "/test", "POST", {}); render(); message("连接成功，发现 " + state.mcp_servers[selectedServer].tools.length + " 个工具。请到 Agent 配置中勾选。"); }))));
  if (selectedServer) form.append(el("div", {class:"actions"}, button("移除服务", () => action(async () => { if (!window.confirm("从服务列表移除「" + server.name + "」？仍被 Agent 使用时不会移除。")) return; state = await request("/mcp/" + encodeURIComponent(selectedServer), "DELETE", {}); selectedServer = null; dirty = false; render(); message("服务已移除。"); }), false, {class:"button danger"})));
  if (server.tested_at) form.append(el("p", {class:"help"}, "最近测试：" + new Date(server.tested_at).toLocaleString("zh-CN")));
  if (server.tools.length) { const catalog = el("div", {class:"note-box"}, el("strong", {}, "发现的工具")); for (const tool of server.tools) catalog.append(el("div", {class:"compact"}, tool.name + " — " + tool.description)); form.append(catalog); }
  content.append(el("div", {class:"layout"}, list, form));
}
const DEFAULT_SKILL = "---\nname: bill-review\ndescription: 核对账单中的金额、日期和机构，列出需要用户确认的差异。\n---\n\n# 账单核对\n\n1. 使用已接入的文件工具提取资料，保留页码和来源。\n2. 区分当期应还金额、剩余本金和授信额度，不重复计入同一笔借款。\n3. 缺失或冲突项标为待确认，影响还款安排时使用 get_user_choice 核对。\n4. 只整理当前对话草稿，不声称已写入长期台账。\n";
async function openSkill(sid, version) {
  const result = await request("/skills/" + encodeURIComponent(sid) + (version ? "?version=" + version : ""));
  selectedSkill = sid; skillFiles = result.files; skillFile = "SKILL.md"; skillVersions = result.versions; viewedVersion = version || result.metadata.version; skillEnabled = result.metadata.enabled; dirty = false; render();
}
function renderSkills() {
  const uploader = input("skill-package", "", {type:"file", accept:".zip,.skill,.md", onchange:event => action(async () => {
    const file = event.target.files[0]; if (!file || !leaveDraft()) return;
    if (file.size > 10 * 1024 * 1024) throw new Error("导入文件最多 10 MiB。");
    if (file.name.endsWith(".md")) { selectedSkill = null; viewedVersion = null; skillEnabled = true; skillFiles = {"SKILL.md":await file.text()}; skillFile = "SKILL.md"; dirty = true; render(); message("已载入 Markdown，请检查后保存 Skill。"); return; }
    const response = await fetch(API + "/skills/import?revision=" + state.revision, {method:"POST", headers:{"Content-Type":"application/zip"}, body:file});
    const result = await response.json(); if (!response.ok) throw new Error(result.detail || "导入失败。");
    const added = Object.keys(result.skills).find(x => !state.skills[x]); state = result; dirty = false;
    if (added) await openSkill(added); else render(); message("Skill 已导入。到 Agent 配置中勾选后生效。");
  })});
  content.append(pageHead("SKILL LIBRARY", "Skill 库", "把业务流程和参考资料整理为可复用的技能。", el("div", {class:"actions"}, el("label", {class:"button upload-label"}, "导入 Skill", uploader), button("新建 Skill", () => { if (!leaveDraft()) return; selectedSkill = null; skillFiles = {"SKILL.md":DEFAULT_SKILL}; skillFile = "SKILL.md"; viewedVersion = null; skillEnabled = true; dirty = false; render(); }, true))));
  const list = el("div", {});
  for (const skill of Object.values(state.skills)) list.append(el("button", {class:"list-card" + (selectedSkill === skill.id ? " selected" : ""), onclick:() => action(async () => { if (leaveDraft()) await openSkill(skill.id); })}, el("strong", {}, skill.id), el("small", {}, skill.description), badge("v" + skill.version + (skill.enabled ? " · 可用" : " · 停用"), skill.enabled)));
  if (!Object.keys(state.skills).length) list.append(empty("Skill 库是空的。可以创建，也可以导入已有技能。"));
  if (!Object.keys(skillFiles).length) skillFiles = {"SKILL.md":DEFAULT_SKILL};
  const metadata = state.skills[selectedSkill];
  const historical = metadata && viewedVersion !== metadata.version;
  const editor = el("section", {class:"panel"}, el("div", {class:"section-head"}, el("h2", {}, selectedSkill || "新建 Skill"), metadata ? badge("当前 v" + metadata.version) : badge("草稿")));
  editor.append(el("p", {class:"help"}, "支持完整 ZIP / .skill 包：SKILL.md、references/、scripts/、assets/。文本与脚本可编辑，图片、PDF、表格等二进制资源原样保留。"));
  const runtime = state.script_runtime;
  editor.append(el("div", {class:"note-box"}, "脚本运行：" + (runtime?.description || "尚未检测") + "。直接支持 Python (.py)、Shell (.sh / .bash)，单次最多 30 秒；不自动安装依赖。包导入后仍需在 Agent 配置中勾选。"));
  const area = el("textarea", {id:"skill-content", class:"code-area", value:skillFiles[skillFile] || "", readOnly:!!historical, oninput:() => { skillFiles[skillFile] = area.value; changed(); }, "aria-label":"Skill 文件内容"});
  const binaryPanel = el("div", {class:"note-box"});
  function showFile() {
    const value = skillFiles[skillFile];
    const binary = typeof value !== "string";
    area.hidden = binary; binaryPanel.hidden = !binary;
    if (!binary) area.value = value || "";
    else {
      area.value = "";
      binaryPanel.replaceChildren(el("p", {}, skillFile + " · " + value.size + " 字节。二进制文件保留原内容，保存新版本时不会丢失。"), button("下载此文件", () => {
        const bytes = Uint8Array.from(atob(value.data), c => c.charCodeAt(0));
        const url = URL.createObjectURL(new Blob([bytes], {type:"application/octet-stream"}));
        const link = el("a", {href:url, download:skillFile.split("/").pop()});
        document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      }));
    }
  }
  const filePicker = select("skill-file", Object.keys(skillFiles).map(n => [n,n]), skillFile, event => { skillFile = event.target.value; showFile(); });
  editor.append(field("当前文件", filePicker), area, binaryPanel); showFile();
  if (!historical) {
    const path = input("resource-path", "", {placeholder:"references/fees.md", "aria-label":"新资源文件路径"});
    editor.append(el("div", {class:"file-actions actions"}, path, button("添加文本或脚本", () => {
      const name = path.value.trim();
      if (!/^(references|assets|scripts)\/[^\\:]+$/.test(name) || name.includes("..") || skillFiles[name] !== undefined) { message("请使用未存在的 references/、scripts/ 或 assets/ 文件路径。", true); return; }
      skillFiles[name] = ""; skillFile = name; changed(); render();
    })));
    const resourceUpload = input("skill-resource-upload", "", {type:"file", onchange:event => action(async () => {
      const file = event.target.files[0]; if (!file) return;
      if (file.size > 10 * 1024 * 1024) throw new Error("单个资源最多 10 MiB。");
      const name = "assets/" + file.name;
      if (skillFiles[name] !== undefined) throw new Error("同名资源已存在，请先换一个文件名。");
      const bytes = new Uint8Array(await file.arrayBuffer());
      let value;
      try { value = new TextDecoder("utf-8", {fatal:true}).decode(bytes); if (value.includes("\0")) throw new Error(); }
      catch { let encoded=""; for (let i=0; i<bytes.length; i+=8192) encoded += String.fromCharCode(...bytes.subarray(i,i+8192)); value={encoding:"base64",data:btoa(encoded),size:bytes.length}; }
      skillFiles[name] = value; skillFile = name; changed(); render();
    })});
    editor.append(el("label", {class:"button upload-label"}, "添加资源文件到 assets/", resourceUpload));
  }
  const enabled = el("input", {type:"checkbox", checked:skillEnabled, disabled:!!historical, onchange:event => { skillEnabled = event.target.checked; changed(); }});
  editor.append(el("label", {class:"check-row"}, enabled, "允许 Agent 选择此 Skill"));
  editor.append(el("div", {class:"actions"}, button("保存 Skill", () => action(async () => {
    const previousIds = new Set(Object.keys(state.skills));
    state = await request("/skills" + (selectedSkill ? "/" + encodeURIComponent(selectedSkill) : ""), selectedSkill ? "PUT" : "POST", {files:skillFiles, enabled:skillEnabled});
    const newId = selectedSkill || Object.keys(state.skills).find(sid => !previousIds.has(sid));
    dirty = false; if (newId) await openSkill(newId); else { skillFiles = {}; render(); }
    message("Skill 已保存为新版本；需在 Agent 配置中勾选后使用。");
  }), true, {disabled:!!historical})));
  if (metadata) {
    const versionSelect = select("skill-version", skillVersions.map(v => [String(v), "v" + v + (v === metadata.version ? "（当前）" : "")]), String(viewedVersion), event => action(async () => { if (leaveDraft()) await openSkill(selectedSkill, Number(event.target.value)); }));
    editor.append(el("div", {class:"actions"}, field("查看历史版本", versionSelect), historical ? button("恢复为新版本", () => action(async () => { state = await request("/skills/" + encodeURIComponent(selectedSkill) + "/restore/" + viewedVersion, "POST", {}); await openSkill(selectedSkill); message("已恢复，原版本仍保留。"); })) : null));
    editor.append(el("div", {class:"actions"}, button("移出 Skill 库", () => action(async () => {
      if (!window.confirm("移出「" + selectedSkill + "」？仍被 Agent 使用时不会移出，磁盘历史版本会保留。")) return;
      state = await request("/skills/" + encodeURIComponent(selectedSkill), "DELETE", {}); selectedSkill = null; skillFiles = {}; viewedVersion = null; dirty = false; render(); message("已移出 Skill 库，历史文件保留在项目目录中。");
    }), false, {class:"button danger"})));
  }
  content.append(el("div", {class:"layout"}, list, editor));
}
document.querySelectorAll(".nav-item").forEach(node => node.addEventListener("click", () => switchView(node.dataset.view)));
function closeEmbedded() {
  if (embedded && leaveDraft()) window.parent.postMessage({type:"adk-capabilities:close"}, location.origin);
}
if (embedded) {
  window.addEventListener("message", event => {
    if (event.origin === location.origin && event.source === window.parent && event.data?.type === "adk-capabilities:request-close") closeEmbedded();
  });
  window.addEventListener("keydown", event => {
    if (event.key === "Escape") { event.preventDefault(); closeEmbedded(); }
  });
  window.parent.postMessage({type:"adk-capabilities:ready"}, location.origin);
}
window.addEventListener("beforeunload", event => { if (dirty) { event.preventDefault(); event.returnValue = ""; } });
request("/state").then(result => { state = result; selectedAgent = new URLSearchParams(location.search).get("app") || "credit_manager"; document.getElementById("connection").textContent = "配置已连接"; render(); }).catch(error => { document.getElementById("connection").textContent = "连接失败"; message(error.message, true); });
