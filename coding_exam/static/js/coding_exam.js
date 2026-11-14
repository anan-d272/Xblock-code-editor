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
   * 1. Default starter code fallback                                   *
   * ------------------------------------------------------------------ */
  var DEFAULT_STARTER = {
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

  var LANG_LABELS = {
    python: "Python",
    java: "Java",
    cpp: "C++",
  };

  /* ------------------------------------------------------------------ *
   * 2. DOM references — all scoped to `element`                        *
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
  var initData = {
    language: "python",
    allowed_languages: ["python"],
    starter_code: {},
    drafts: {},
    visible_test_cases: [],
  };

  try {
    var rawInit = element.querySelector(".ce-init-data");
    if (rawInit && rawInit.textContent) {
      initData = JSON.parse(rawInit.textContent);
    }
  } catch (e) {
    console.warn("[CodingExamXBlock] could not parse init data:", e);
  }

  var allowedLangs = (initData.allowed_languages && initData.allowed_languages.length > 0)
    ? initData.allowed_languages
    : ["python"];

  var drafts = Object.assign({}, initData.drafts || {});
  var starterMap = Object.assign({}, DEFAULT_STARTER, initData.starter_code || {});

  // Ensure current language is valid for this problem
  var currentLang = initData.language || "python";
  if (allowedLangs.indexOf(currentLang) === -1) {
    currentLang = allowedLangs[0];
  }

  // Populate language dropdown dynamically based on allowed languages
  langSelect.innerHTML = "";
  allowedLangs.forEach(function (langKey) {
    var opt = document.createElement("option");
    opt.value = langKey;
    opt.textContent = LANG_LABELS[langKey] || langKey;
    if (langKey === currentLang) {
      opt.selected = true;
    }
    langSelect.appendChild(opt);
  });

  // If only 1 allowed language, disable dropdown to prevent confusion
  if (allowedLangs.length <= 1) {
    langSelect.disabled = true;
  }

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
    // Return saved draft if available; fall back to author's starter template.
    if (drafts[lang] !== undefined) {
      return drafts[lang];
    }
    return starterMap[lang] || "";
  }

  var langCompartment = new Compartment();
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
          drafts[currentLang] = code;
          debouncedSave(currentLang, code);
        }),
      ],
    }),
    parent: editorEl,
  });

  /* ------------------------------------------------------------------ *
   * 7. Language switcher                                               *
   * ------------------------------------------------------------------ */
  langSelect.addEventListener("change", function () {
    var newLang = langSelect.value;
    if (newLang === currentLang) { return; }

    // Persist current content before switching
    drafts[currentLang] = view.state.doc.toString();
    currentLang = newLang;

    // Swap editor content + syntax mode in a single transaction
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
   * 8. Run button (Executes visible tests via Teerth's runner)          *
   * ------------------------------------------------------------------ */
  var runUrl = runtime.handlerUrl(element, "run_code");

  runBtn.addEventListener("click", function () {
    var code = view.state.doc.toString();
    var lang = currentLang;

    runBtn.disabled    = true;
    runBtn.textContent = "Running\u2026";
    runMsg.textContent = "";

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
        outputPre.textContent = "Error: " + result.error;
        outputPre.classList.add("has-error");
        outputPanel.classList.add("visible");
        return;
      }

      // Check if multi-test response structure is present
      if (result.results && Array.isArray(result.results)) {
        var lines = [];
        var total = result.total_count || result.results.length;
        var passed = result.passed_count || 0;

        lines.push("=== Sample Test Results (" + passed + "/" + total + " Passed) ===");

        if (result.compilation_error) {
          lines.push("\n[Compilation Error]\n" + result.compilation_error);
        }

        result.results.forEach(function (tc, idx) {
          var statusMark = tc.passed ? "✓ PASSED" : "✗ FAILED";
          var header = "\n--- Case #" + (idx + 1) + ": " + statusMark + " (" + tc.status + ") ---";
          lines.push(header);

          if (tc.input && tc.input !== "[Hidden]") {
            lines.push("Input:\n" + tc.input.trim());
          }
          if (tc.expected_output && tc.expected_output !== "[Hidden]") {
            lines.push("Expected Output:\n" + tc.expected_output.trim());
          }
          if (tc.actual_output && tc.actual_output !== "[Hidden]") {
            lines.push("Actual Output:\n" + tc.actual_output.trim());
          }
          if (tc.error_message) {
            lines.push("Error Detail:\n" + tc.error_message);
          }
        });

        if (result.feedback) {
          lines.push("\nSummary: " + result.feedback);
        }

        outputPre.textContent = lines.join("\n");
        if (passed === total && !result.compilation_error) {
          outputPre.classList.remove("has-error");
        } else {
          outputPre.classList.add("has-error");
        }
        outputPanel.classList.add("visible");
        return;
      }

      // Fallback single-run display
      var parts = [];
      if (result.stdout)         { parts.push(result.stdout); }
      if (result.compile_output) { parts.push("[Compile output]\n" + result.compile_output); }
      if (result.stderr)         { parts.push("[stderr]\n" + result.stderr); }

      var outputText = parts.join("\n").trim() || "(no output)";
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
