/* Per-Agent model thinking. Uses the native node, YAML and Save/Cancel lifecycle. */
(() => {
  "use strict";
  let scheduled = false;
  const row = document.createElement("section");
  row.id = "adk-model-thinking";
  const label = document.createElement("label");
  const title = document.createElement("span");
  title.textContent = "思考模式";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.id = "adk-model-thinking-toggle";
  input.setAttribute("role", "switch");
  input.setAttribute("aria-describedby", "adk-model-thinking-hint");
  const track = document.createElement("span");
  track.className = "adk-thinking-track";
  track.setAttribute("aria-hidden", "true");
  label.append(title, input, track);
  const hint = document.createElement("p");
  hint.id = "adk-model-thinking-hint";
  row.append(label, hint);

  function selectedConfig() {
    return window.__adkModelEditor?.agentConfig;
  }
  function defaults() { return window.__adkThinkingDefaults || {}; }
  function mode(config) {
    return config.generate_content_config?.http_options?.extra_body?.thinking?.type
      ?? defaults()[config.model] ?? "disabled";
  }
  input.addEventListener("change", () => {
    const config = selectedConfig();
    if (!config || input.disabled) return;
    // Copy only the changed branch: preserve temperature, headers, other
    // provider options and the native node identity used by graph + Save.
    const generation = config.generate_content_config || {};
    const http = generation.http_options || {};
    config.generate_content_config = {
      ...generation,
      http_options: {
        ...http,
        extra_body: {...http.extra_body, thinking: {type: input.checked ? "enabled" : "disabled"}}
      }
    };
    window.__adkModelEditor?.cdr?.markForCheck();
    mount();
  });
  function mount() {
    scheduled = false;
    const config = selectedConfig();
    const field = [...document.querySelectorAll("app-builder-tabs mat-form-field")]
      .find(element => element.querySelector("mat-label")?.textContent.trim() === "Model");
    if (!field || !config || config.agent_class !== "LlmAgent") {
      row.remove();
      return;
    }
    if (field.nextElementSibling !== row) field.after(row);
    const supported = Object.hasOwn(defaults(), config.model);
    const valid = ["enabled", "disabled"].includes(mode(config));
    input.disabled = !supported || !valid;
    input.checked = mode(config) === "enabled";
    const text = !supported ? "当前模型未接入思考配置。"
      : !valid ? "思考配置无效，请检查 Agent YAML。"
      : "仅应用于当前 Agent；点击 Save 保存，新建会话后使用。开启后通常需要更长时间。";
    if (hint.textContent !== text) hint.textContent = text;
  }
  function schedule() {
    if (!scheduled) { scheduled = true; requestAnimationFrame(mount); }
  }
  window.addEventListener("adk:model-editor", schedule);
  new MutationObserver(schedule).observe(document.body, {childList:true, subtree:true});
  mount();
})();
