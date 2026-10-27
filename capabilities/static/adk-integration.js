/* ADK 2.12 extension: page-local capability settings, no bundled-JS edits. */
(() => {
  "use strict";
  const origin = location.origin;
  let snapshot, loading = false, scheduled = false, activeApp = null, returnFocus, frameReady = false;
  function currentApp() { return new URLSearchParams(location.search).get("app") || ""; }
  function node(tag, attrs = {}, text) {
    const element = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
    if (text) element.textContent = text;
    return element;
  }
  const dialog = node("dialog", {id:"adk-capability-dialog", "aria-labelledby":"adk-capability-title"});
  const heading = node("h2", {id:"adk-capability-title"}, "MCP / Skill 配置");
  const context = node("span", {class:"adk-capability-context"});
  const close = node("button", {type:"button", class:"adk-capability-close", "aria-label":"关闭能力配置，返回 ADK"}, "返回编辑 ×");
  const bar = node("div", {class:"adk-capability-bar"});
  bar.append(heading, context, close);
  const frame = node("iframe", {title:"MCP 与 Skill 配置面板", referrerpolicy:"same-origin"});
  dialog.append(bar, frame);
  document.body.append(dialog);

  function open(view = "agents") {
    if (dialog.open) return;
    returnFocus = document.activeElement;
    activeApp = currentApp();
    frameReady = false;
    context.textContent = activeApp ? "当前 Agent · " + activeApp : "选择 Agent 后配置能力";
    heading.textContent = view === "models" ? "模型引擎" : "MCP / Skill 配置";
    frame.src = "/capabilities?embedded=1&view=" + view + "&app=" + encodeURIComponent(activeApp);
    dialog.showModal();
    close.focus();
  }
  function requestClose() {
    // Let the editor handle unsaved changes. If it failed to load, just close.
    if (frameReady) {
      frame.contentWindow.postMessage({type:"adk-capabilities:request-close"}, origin);
    } else finishClose();
  }
  function finishClose() {
    dialog.close();
    frame.removeAttribute("src");
    activeApp = null;
    frameReady = false;
    if (returnFocus?.isConnected) returnFocus.focus();
    refresh();
  }
  close.addEventListener("click", requestClose);
  dialog.addEventListener("cancel", event => { event.preventDefault(); requestClose(); });
  window.addEventListener("message", event => {
    if (event.origin !== origin || event.source !== frame.contentWindow || !dialog.open) return;
    if (event.data?.type === "adk-capabilities:ready") frameReady = true;
    if (event.data?.type === "adk-capabilities:close") finishClose();
    if (event.data?.type === "adk-model-engines:changed") window.dispatchEvent(new Event("adk:model-engines-changed"));
  });
  window.addEventListener("adk:open-model-engines", () => open("models"));

  function updateSummary() {
    const card = document.getElementById("adk-capability-card");
    if (!card) return;
    const app = currentApp(), binding = snapshot?.agents?.[app] || {mcp:[],skills:[]};
    const summary = !app ? "先选择或保存一个 Agent，再配置它的能力。"
      : !snapshot ? "配置状态暂不可用，可打开面板重试。"
      : binding.mcp.reduce((total, item) => total + item.tools.length, 0) + " 个 MCP 工具 · " + binding.skills.length + " 个 Skill";
    const text = card.querySelector(".adk-capability-summary");
    if (text.textContent !== summary) text.textContent = summary;
    const detail = card.querySelector(".adk-capability-detail");
    const label = app ? "应用于「" + app + "」；保存后下一次调用生效。" : "服务和 Skill 在工作空间统一维护。";
    if (detail.textContent !== label) detail.textContent = label;
  }
  async function refresh() {
    if (loading) return;
    loading = true;
    try {
      const response = await fetch("/capabilities/api/state");
      if (!response.ok) throw new Error("unavailable");
      snapshot = await response.json();
    } catch { snapshot = null; }
    finally { loading = false; updateSummary(); }
  }
  function mount() {
    scheduled = false;
    const toolbar = document.querySelector("mat-toolbar.app-toolbar");
    if (toolbar && !document.getElementById("adk-capability-entry")) {
      const button = node("button", {id:"adk-capability-entry", type:"button", class:"adk-capability-entry", "aria-haspopup":"dialog", title:"配置 MCP 服务、Skill 与当前 Agent 的能力"}, "MCP / Skill 配置");
      button.addEventListener("click", () => open());
      toolbar.insertBefore(button, toolbar.querySelector(".user-avatar-button"));
      const models = node("button", {id:"adk-model-engine-entry", type:"button", class:"adk-capability-entry", "aria-haspopup":"dialog"}, "模型引擎");
      models.addEventListener("click", () => open("models"));
      button.before(models);
    }
    const actions = document.querySelector("app-builder-tabs .action-buttons");
    if (actions && !document.getElementById("adk-capability-card")) {
      const card = node("section", {id:"adk-capability-card", "aria-label":"MCP 与 Skill"});
      card.append(node("h3", {}, "MCP 与 Skill"), node("p", {class:"adk-capability-summary"}), node("p", {class:"adk-capability-detail"}));
      const button = node("button", {type:"button", class:"adk-capability-configure", "aria-haspopup":"dialog"}, "配置服务与技能");
      button.addEventListener("click", () => open());
      card.append(button);
      actions.before(card);
    }
    updateSummary();
  }
  // Angular owns its components: remount only our small, isolated nodes when
  // the user enters/leaves Builder. Do not touch native form values or Save.
  const observer = new MutationObserver(() => {
    if (!scheduled) { scheduled = true; requestAnimationFrame(mount); }
  });
  observer.observe(document.body, {childList:true, subtree:true});
  window.addEventListener("focus", refresh);
  mount(); refresh();
})();
