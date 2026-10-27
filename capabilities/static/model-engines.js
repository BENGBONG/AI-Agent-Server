"use strict";
let modelState = null, selectedEngine = "deepseek", modelLoad = 0;

async function modelRequest(path = "", method = "GET", body) {
  const options = {method, headers:{}};
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify({...body, revision:modelState.revision});
  }
  const response = await fetch("/capabilities/api/models" + path, options);
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 409) {
      // Keep the form intact. A deliberate save after this message may retry
      // against the fresh revision instead of trapping users in a 409 loop.
      modelState = await modelRequest();
    }
    throw new Error(typeof result.detail === "string" ? result.detail : "连接未完成，请检查输入后重试。");
  }
  return result;
}

function notifyModelChange() {
  if (embedded) window.parent.postMessage({type:"adk-model-engines:changed"}, location.origin);
}

async function renderModels() {
  const sequence = ++modelLoad;
  if (!modelState) {
    content.append(el("h1", {}, "模型引擎"), el("p", {class:"help", role:"status"}, "正在读取模型连接…"));
    try { modelState = await modelRequest(); }
    catch (error) { message(error.message, true); return; }
    if (view !== "models" || sequence !== modelLoad) return;
    content.replaceChildren();
  }
  const config = modelState.engines[selectedEngine];
  const currentDefault = modelState.catalog.find(item => item.reference === modelState.default_model);
  const defaultName = currentDefault ? modelState.engines[currentDefault.engine].name + " · " + currentDefault.model : modelState.default_model;
  content.append(el("div", {class:"page-head"}, el("div", {}, el("h1", {}, "模型引擎"), el("p", {class:"intro"}, "配置模型连接，在 Agent 编辑页选择使用。"))));
  const list = el("div", {class:"engine-list", "aria-label":"选择模型引擎"});
  for (const [id, item] of Object.entries(modelState.engines)) {
    list.append(el("button", {type:"button", class:"list-card" + (id === selectedEngine ? " selected" : ""), "aria-pressed":String(id === selectedEngine), onclick:() => {
      if (id === selectedEngine || !leaveDraft()) return;
      selectedEngine = id; dirty = false; notice.hidden = true; render();
    }}, el("strong", {}, item.name), el("small", {}, item.has_key ? "Key 已配置" : "待填写 Key"), currentDefault?.engine === id ? badge("新 Agent 默认", true) : null));
  }
  const editor = el("section", {class:"panel engine-editor", "aria-label":config.name + " 连接设置"},
    el("div", {class:"section-head"}, el("h2", {}, config.name), badge(config.has_key ? "Key 已配置" : "待配置", config.has_key)));
  const testStatus = el("div", {class:"engine-test-result", role:"status", "aria-live":"polite", hidden:true});
  function change() { changed(); testStatus.hidden = true; }
  const base = input("engine-api-base", config.api_base, {type:"url", required:true, spellcheck:false, oninput:change});
  const key = input("engine-api-key", "", {type:"password", autocomplete:"new-password", spellcheck:false, placeholder:config.has_key ? "已配置；留空保留原 Key" : "输入 " + config.name + " API Key", oninput:change});
  const showKey = button("显示", () => { key.type = key.type === "password" ? "text" : "password"; showKey.textContent = key.type === "password" ? "显示" : "隐藏"; }, false, {"aria-label":"显示或隐藏本次输入的 Key"});
  const clear = input("engine-clear-key", "", {type:"checkbox", disabled:!config.has_key, onchange:() => { key.disabled = clear.checked; showKey.disabled = clear.checked; change(); }});
  const model = input("engine-model-id", config.models[0], {list:"engine-model-options", required:true, spellcheck:false, oninput:change});
  const suggestions = el("datalist", {id:"engine-model-options"}, config.models.map(id => el("option", {value:id})));
  const extra = el("textarea", {id:"engine-extra-models", rows:3, value:config.models.slice(1).join("\n"), spellcheck:false, oninput:change});
  const more = el("details", {class:"engine-more"}, el("summary", {}, "添加更多可选模型"), field("其他模型 ID（每行一个）", extra, "保存后，这些模型也会出现在该引擎的 Agent 模型列表中。"));
  editor.append(field("API Base URL", base, "填写 API 根地址，不包含 /chat/completions 或 /messages。"),
    field("API Key", el("div", {id:"engine-key-field", class:"engine-key-row"}, key, showKey), "仅保存到本机；已保存的 Key 不会回显。也可使用 " + config.key_env + " 环境变量。"),
    el("label", {class:"check-row", htmlFor:clear.id}, clear, "清除已保存的 Key"),
    field("模型 ID", model, "填写此账户可用的对话模型 ID；OpenRouter 使用完整 ID，例如 openai/gpt-4.1-mini。"), suggestions, more);
  // Associate the Key label with the password control, rather than its wrapper.
  editor.querySelector('label[for="engine-key-field"]').htmlFor = key.id;
  function draft() {
    return {settings:{api_base:base.value.trim(), models:[...new Set([model.value.trim(), ...extra.value.split(/\n/).map(id => id.trim()).filter(Boolean)])]}, api_key:clear.checked ? "" : key.value.trim(), clear_key:clear.checked};
  }
  async function run(task) {
    const controls = [...content.querySelectorAll("input,textarea,select,button")].map(node => [node, node.disabled]);
    controls.forEach(([node]) => node.disabled = true);
    editor.setAttribute("aria-busy", "true");
    try { await task(); }
    catch (error) { testStatus.hidden = false; testStatus.className = "engine-test-result error"; testStatus.textContent = error.message; }
    finally { controls.forEach(([node, disabled]) => node.disabled = disabled); editor.removeAttribute("aria-busy"); }
  }
  const test = button("测试连接", () => run(async () => {
    testStatus.hidden = false; testStatus.className = "engine-test-result"; testStatus.textContent = "正在发送简短测试消息…";
    const result = await modelRequest("/" + selectedEngine + "/test", "POST", draft());
    testStatus.className = "engine-test-result success";
    testStatus.textContent = result.message + " " + result.model + " · " + result.latency_ms + " ms。本次测试未保存配置。";
  }));
  const discover = button("获取模型列表", () => run(async () => {
    const result = await modelRequest("/" + selectedEngine + "/test", "POST", {...draft(), purpose:"models"});
    suggestions.replaceChildren(...result.models.map(id => el("option", {value:id})));
    testStatus.hidden = false; testStatus.className = "engine-test-result";
    testStatus.textContent = "已读取 " + result.models.length + " 个模型。点击模型 ID 输入框选择；当前输入不会被覆盖。";
    model.focus();
  }));
  const save = button("保存引擎配置", () => run(async () => {
    const id = selectedEngine;
    modelState = await modelRequest("/" + id, "PUT", draft());
    key.value = "";
    notifyModelChange();
    if (view === "models" && selectedEngine === id) { dirty = false; render(); message("已保存 " + config.name + "。当前 ADK 编辑页已更新模型列表，可选择模型并点击 Save。"); }
  }), true);
  editor.append(el("div", {class:"engine-actions"}, test, discover, save),
    el("p", {class:"help"}, "测试连接会发送一条简短消息，可能产生少量 API 用量。测试不保存；保存不修改任何 Agent 的模型。"), testStatus);
  const setDefault = button("设为新 Agent 默认", () => run(async () => {
    const reference = modelState.catalog.find(item => item.engine === selectedEngine && item.model === model.value.trim())?.reference;
    if (dirty || !reference) throw new Error("请先保存引擎配置，再设置默认模型。");
    modelState = await modelRequest("/default", "PUT", {reference});
    notifyModelChange();
    if (view === "models") { render(); message("默认模型已保存。刷新 ADK 页面后用于新建 Agent；已有 Agent 的模型保持原选择。"); }
  }), false, {disabled:!config.has_key});
  content.append(el("div", {class:"layout engine-layout"}, list, editor),
    el("section", {class:"engine-default"}, el("div", {}, el("strong", {}, "新 Agent 默认模型"), el("p", {class:"help"}, defaultName)), setDefault));
}
