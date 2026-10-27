/* Model engine selection stays inside the native Agent Save/Cancel lifecycle. */
(() => {
  "use strict";
  let state, scheduled = false, loading = false;
  const section = document.createElement("section");
  section.id = "adk-model-engine";
  const label = document.createElement("label");
  label.htmlFor = "adk-model-engine-select"; label.textContent = "模型引擎";
  const select = document.createElement("select");
  select.id = label.htmlFor;
  const manage = document.createElement("button");
  manage.type = "button"; manage.textContent = "连接设置";
  manage.addEventListener("click", () => window.dispatchEvent(new Event("adk:open-model-engines")));
  const controls = document.createElement("div"); controls.className = "adk-engine-controls";
  controls.append(select, manage);
  const hint = document.createElement("p"); hint.id = "adk-model-engine-hint";
  select.setAttribute("aria-describedby", hint.id);
  section.append(label, controls, hint);

  function engineFor(reference) {
    return state?.catalog.find(item => item.reference === reference)?.engine
      || (reference?.startsWith("engine/") ? reference.split("/")[1] : "deepseek");
  }
  function apply(model) {
    const editor = window.__adkModelEditor;
    if (!editor?.agentConfig) return;
    editor.agentConfig.model = model;
    editor.cdr?.detectChanges();
    window.dispatchEvent(new Event("adk:model-editor"));
    mount();
  }
  select.addEventListener("change", () => {
    const available = state.catalog.filter(item => item.engine === select.value);
    if (available.length) apply(available[0].reference);
  });
  async function refresh() {
    if (loading) return;
    loading = true;
    try {
      const response = await fetch("/capabilities/api/models");
      if (!response.ok) throw new Error();
      state = await response.json();
      const options = Object.entries(state.engines).map(([id, item]) => {
        const option = document.createElement("option"); option.value = id;
        option.textContent = item.name + (item.has_key ? "" : "（未配置 Key）");
        return option;
      });
      select.replaceChildren(...options);
      window.__adkModelLabels = Object.fromEntries(state.catalog.map(item => [item.reference, item.model]));
      // Restrict the existing thinking switch to its verified DeepSeek protocol.
      const defaults = window.__adkThinkingDefaults || {};
      for (const item of state.catalog.filter(item => item.engine === "deepseek")) defaults[item.reference] ??= "disabled";
      window.__adkThinkingDefaults = defaults;
    } catch { state = null; }
    finally { loading = false; mount(); }
  }
  function mount() {
    scheduled = false;
    const editor = window.__adkModelEditor, config = editor?.agentConfig;
    const field = [...document.querySelectorAll("app-builder-tabs mat-form-field")]
      .find(element => element.querySelector("mat-label")?.textContent.trim() === "Model");
    if (!field || !config || config.agent_class !== "LlmAgent") { section.remove(); return; }
    if (field.previousElementSibling !== section) field.before(section);
    if (!state) { select.disabled = true; hint.textContent = "连接配置未读取，请打开连接设置重试。"; return; }
    select.disabled = false;
    const engine = engineFor(config.model), settings = state.engines[engine];
    select.value = engine;
    const models = state.catalog.filter(item => item.engine === engine).map(item => item.reference);
    if (config.model && !models.includes(config.model)) models.push(config.model);
    if (JSON.stringify(editor.models) !== JSON.stringify(models)) {
      editor.models = models;
      editor.cdr?.detectChanges();
    }
    const text = !settings ? "当前模型没有对应的引擎配置。"
      : !settings.has_key ? "请先在连接设置中填写 " + settings.name + " 的 Key。选择模型后点击 Save 保存。"
      : "仅修改当前 Agent；点击 Save 保存，Cancel 放弃。";
    if (hint.textContent !== text) hint.textContent = text;
  }
  function schedule() { if (!scheduled) { scheduled = true; requestAnimationFrame(mount); } }
  window.addEventListener("adk:model-editor", schedule);
  window.addEventListener("adk:model-engines-changed", refresh);
  window.addEventListener("focus", refresh);
  new MutationObserver(schedule).observe(document.body, {childList:true, subtree:true});
  refresh();
})();
