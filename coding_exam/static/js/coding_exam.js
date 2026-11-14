/* global CM */
/**
 * CodingExamXBlock — student-side initialization.
 *
 * Called by the LMS runtime as: CodingExamXBlock(runtime, element)
 *   - runtime : XBlock JS runtime (provides handlerUrl)
 *   - element : DOM root of this XBlock fragment instance
 *
 * Requires window.CM (CodeMirror 6 IIFE bundle) loaded before this file.
 */
function CodingExamXBlock(runtime, element) {   // eslint-disable-line no-unused-vars
  "use strict";

  /* ------------------------------------------------------------------ *
   * 1. Starter code — shown when a student has no saved draft yet       *
   * ------------------------------------------------------------------ */
  var STARTER = {
    python: [
      "# Write your Python solution here",
      "",
      "def main():",
      "    pass  # TODO: implement",
      "",
      "if __name__ == '__main__':",
      "    main()",
    ].join("\n"),

    java: [
      "public class Main {",
      "    public static void main(String[] args) {",
      "        // TODO: implement",
      "    }",
      "}",
    ].join("\n"),

    cpp: [
      "#include <iostream>",
      "using namespace std;",
      "",
      "int main() {",
      "    // TODO: implement",
      "    return 0;",
      "}",
    ].join("\n"),
  };

  /* ------------------------------------------------------------------ *
   * 2. DOM references — all scoped to `element` to support multiple    *
   *    instances on the same page.                                      *
   * ------------------------------------------------------------------ */
  var langSelect  = element.querySelector(".ce-lang-select");
  var editorEl    = element.querySelector(".ce-editor-container");
  var saveStatus  = element.querySelector(".ce-save-status");
  var runBtn      = element.querySelector(".ce-run-btn");
  var runMsg      = element.querySelector(".ce-run-msg");
  var outputPanel = element.querySelector(".ce-output-panel");
  var outputPre   = element.querySelector(".ce-output");

  /* ------------------------------------------------------------------ *
   * 3. Load initial state embedded as JSON by block.py                 *
   * ------------------------------------------------------------------ */
  var initData = { language: "python", drafts: {} };
  try {
    initData = JSON.parse(element.querySelector(".ce-init-data").textContent);
  } catch (e) {
    console.warn("[CodingExamXBlock] could not parse init data:", e);
  }

  // In-memory per-language drafts; pre-populated from server state.
  var drafts = Object.assign({}, initData.drafts || {});
  var currentLang = initData.language || "python";

  /* ------------------------------------------------------------------ *
   * 4. Utility: debounce                                               *
   * ------------------------------------------------------------------ */
  function debounce(fn, ms) {
    var timer;
    return function () {
      var args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(null, args); }, ms);
    };
  }

  /* ------------------------------------------------------------------ *
   * 5. Save-draft: debounced POST to save_draft handler                *
   * ------------------------------------------------------------------ */
  var saveUrl = runtime.handlerUrl(element, "save_draft");

  function setSaveStatus(msg, cls) {
    saveStatus.textContent = msg;
    saveStatus.className   = "ce-save-status" + (cls ? " " + cls : "");
  }

  function saveDraft(lang, code) {
    setSaveStatus("Saving\u2026", "saving");
    fetch(saveUrl, {
      method  : "POST",
      headers : { "Content-Type": "application/json" },
      body    : JSON.stringify({ language: lang, code: code }),
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) {
        setSaveStatus("Save failed", "");
        console.warn("[CodingExamXBlock] save_draft error:", data.error);
      } else {
        setSaveStatus("Saved \u2713", "saved");
        setTimeout(function () { setSaveStatus("", ""); }, 2000);
      }
    })
    .catch(function (err) {
      setSaveStatus("Save failed", "");
      console.error("[CodingExamXBlock] save_draft fetch error:", err);
    });
  }

  // Fire 1 second after the student stops typing.
  var debouncedSave = debounce(saveDraft, 1000);

  /* ------------------------------------------------------------------ *
   * 6. CodeMirror 6 editor setup                                       *
   * ------------------------------------------------------------------ */
  var EditorView  = CM.EditorView;
  var EditorState = CM.EditorState;
  var Compartment = CM.Compartment;
  var basicSetup  = CM.basicSetup;

  var langExtMap = { python: CM.python, java: CM.java, cpp: CM.cpp };

  function getLangExt(lang) {
    var fn = langExtMap[lang];
    return fn ? fn() : [];
  }

  function getCode(lang) {
    // Return saved draft if available; fall back to language starter template.
    return (drafts[lang] !== undefined) ? drafts[lang] : (STARTER[lang] || "");
  }

  var langCompartment = new Compartment();

  // `view` is declared before creation so the updateListener closure can
  // reference it safely (by the time the listener fires, view is assigned).
  var view;

  view = new EditorView({
    state: EditorState.create({
      doc: getCode(currentLang),
      extensions: [
        basicSetup,
        langCompartment.of(getLangExt(currentLang)),

        // Debounced autosave — fires whenever the document changes.
        EditorView.updateListener.of(function (update) {
          if (!update.docChanged) { return; }
          var code = view.state.doc.toString();
          drafts[currentLang] = code;        // keep in-memory draft current
          debouncedSave(currentLang, code);
        }),
      ],
    }),
    parent: editorEl,
  });

  // Sync the dropdown to the restored language.
  langSelect.value = currentLang;

  /* ------------------------------------------------------------------ *
   * 7. Language switcher                                               *
   * ------------------------------------------------------------------ */
  langSelect.addEventListener("change", function () {
    var newLang = langSelect.value;
    if (newLang === currentLang) { return; }

    // Persist current content before switching.
    drafts[currentLang] = view.state.doc.toString();

    currentLang = newLang;

    // Swap editor content + syntax mode in a single transaction.
    view.dispatch({
      changes: {
        from  : 0,
        to    : view.state.doc.length,
        insert: getCode(newLang),
      },
      effects: langCompartment.reconfigure(getLangExt(newLang)),
    });
  });

  /* ------------------------------------------------------------------ *
   * 8. Run button                                                       *
   * ------------------------------------------------------------------ */
  var runUrl = runtime.handlerUrl(element, "run_code");

  runBtn.addEventListener("click", function () {
    var code = view.state.doc.toString();
    var lang = currentLang;

    // Disable button while running.
    runBtn.disabled    = true;
    runBtn.textContent = "Running\u2026";
    runMsg.textContent = "";

    // Clear previous output.
    outputPre.textContent = "";
    outputPre.className   = "ce-output";
    outputPanel.classList.remove("visible");

    fetch(runUrl, {
      method  : "POST",
      headers : { "Content-Type": "application/json" },
      body    : JSON.stringify({ language: lang, code: code }),
    })
    .then(function (r) { return r.json(); })
    .then(function (result) {
      runBtn.disabled    = false;
      runBtn.textContent = "\u25B6 Run";

      if (result.error) {
        // Validation error returned by the handler (not an execution error).
        outputPre.textContent = "Error: " + result.error;
        outputPre.classList.add("has-error");
        outputPanel.classList.add("visible");
        return;
      }

      // Build the output text from the ExecutionResult dict.
      var parts = [];
      if (result.stdout)         { parts.push(result.stdout); }
      if (result.compile_output) { parts.push("[Compile output]\n" + result.compile_output); }
      if (result.stderr)         { parts.push("[stderr]\n" + result.stderr); }

      var outputText = parts.join("\n").trim() || "(no output)";

      // Append a status/timing footer.
      var footer = "[" + (result.status_description || result.status || "?") + "]";
      if (result.execution_time) { footer += "  time: " + result.execution_time + "s"; }
      outputText += "\n\n" + footer;

      outputPre.textContent = outputText;
      if (!result.is_success) { outputPre.classList.add("has-error"); }

      outputPanel.classList.add("visible");
    })
    .catch(function (err) {
      runBtn.disabled    = false;
      runBtn.textContent = "\u25B6 Run";
      outputPre.textContent = "Network error: " + err.message;
      outputPre.classList.add("has-error");
      outputPanel.classList.add("visible");
      console.error("[CodingExamXBlock] run_code fetch error:", err);
    });
  });
}

