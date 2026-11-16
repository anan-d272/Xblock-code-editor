/* global CM */
/**
 * CodingExamXBlock — student-side initialization (Days 5 & 6).
 *
 * Called by the LMS runtime as: CodingExamXBlock(runtime, element)
 *   - runtime : XBlock JS runtime (provides handlerUrl)
 *   - element : DOM root of this XBlock fragment instance
 *
 * Requires window.CM (CodeMirror 6 IIFE bundle) loaded before this file.
 *
 * Day 5: Run (visible tests) + Submit (all tests), grading, attempt counter.
 * Day 6: Clipboard/drop blocking on the editor, integrity event logging.
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
  var langSelect        = element.querySelector(".ce-lang-select");
  var editorEl          = element.querySelector(".ce-editor-container");
  var saveStatus        = element.querySelector(".ce-save-status");
  var runBtn            = element.querySelector(".ce-run-btn");
  var submitBtn         = element.querySelector(".ce-submit-btn");
  var runMsg            = element.querySelector(".ce-run-msg");
  var attemptsInfo      = element.querySelector(".ce-attempts-info");
  var runPanel          = element.querySelector(".ce-run-panel");
  var runResultsBody    = element.querySelector(".ce-run-results-body");
  var submitPanel       = element.querySelector(".ce-submit-panel");
  var submitScoreSummary = element.querySelector(".ce-submit-score-summary");
  var submitResultsBody = element.querySelector(".ce-submit-results-body");

  /* ------------------------------------------------------------------ *
   * 3. Load initial state embedded as JSON by block.py                 *
   * ------------------------------------------------------------------ */
  var initData = {
    language: "python",
    allowed_languages: ["python"],
    starter_code: {},
    drafts: {},
    visible_test_cases: [],
    points: 10.0,
    max_attempts: 0,
    attempts: 0,
    score: null,
    last_submission: {},
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

  // Attempts bookkeeping from server state
  var currentAttempts = parseInt(initData.attempts || 0, 10);
  var maxAttempts     = parseInt(initData.max_attempts || 0, 10);

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
   * 4. Attempts display                                                *
   * ------------------------------------------------------------------ */
  function updateAttemptsDisplay() {
    if (!attemptsInfo) { return; }
    if (maxAttempts > 0) {
      attemptsInfo.textContent = "Attempts: " + currentAttempts + " / " + maxAttempts;
    } else if (currentAttempts > 0) {
      attemptsInfo.textContent = "Attempts: " + currentAttempts;
    } else {
      attemptsInfo.textContent = "";
    }
    // Disable submit if at limit
    if (submitBtn && maxAttempts > 0 && currentAttempts >= maxAttempts) {
      submitBtn.disabled = true;
      submitBtn.title = "Attempt limit reached.";
    }
  }
  updateAttemptsDisplay();

  // Restore previous score in submit panel if student already submitted
  if (initData.score !== null && initData.score !== undefined && submitPanel) {
    var prev = initData.last_submission || {};
    if (prev.passed_count !== undefined) {
      submitScoreSummary.innerHTML = buildScoreSummaryHTML(
        prev.passed_count, prev.total_count,
        initData.score, float(initData.points || 10.0)
      );
      submitPanel.classList.add("visible");
    }
  }

  /* ------------------------------------------------------------------ *
   * 5. Utility helpers                                                 *
   * ------------------------------------------------------------------ */
  function float(v) { return parseFloat(v) || 0; }

  function debounce(fn, ms) {
    var timer;
    return function () {
      var args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(null, args); }, ms);
    };
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ------------------------------------------------------------------ *
   * 6. Save-draft: debounced POST to save_draft handler               *
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

  var debouncedSave = debounce(saveDraft, 1000);

  /* ------------------------------------------------------------------ *
   * 7. CodeMirror 6 editor setup                                       *
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
   * 8. Language switcher                                               *
   * ------------------------------------------------------------------ */
  langSelect.addEventListener("change", function () {
    var newLang = langSelect.value;
    if (newLang === currentLang) { return; }

    drafts[currentLang] = view.state.doc.toString();
    currentLang = newLang;

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
   * 9. Result rendering helpers                                        *
   * ------------------------------------------------------------------ */
  function buildScoreSummaryHTML(passed, total, score, maxPoints) {
    var scoreStr = (typeof score === "number" ? score.toFixed(2) : "?");
    var maxStr   = (typeof maxPoints === "number" ? maxPoints.toFixed(1) : "?");
    var pct      = total > 0 ? Math.round((passed / total) * 100) : 0;
    var cls      = (passed === total && total > 0) ? "ce-score-pass" : "ce-score-partial";
    return (
      '<div class="ce-score-summary ' + cls + '">' +
        '<span class="ce-score-fraction">' + passed + ' / ' + total + ' tests passed</span>' +
        ' &mdash; ' +
        '<span class="ce-score-points">Score: ' + scoreStr + ' / ' + maxStr + ' pts (' + pct + '%)</span>' +
      '</div>'
    );
  }

  function buildTestResultRows(results) {
    if (!results || results.length === 0) {
      return '<div class="ce-no-results">No results returned.</div>';
    }
    var html = "";
    results.forEach(function (tc, idx) {
      var icon = tc.passed
        ? '<span class="ce-tc-pass">&#10003; PASS</span>'
        : '<span class="ce-tc-fail">&#10007; FAIL</span>';
      var statusLabel = escHtml(tc.status || "");
      var timeStr = tc.execution_time ? (" &mdash; " + parseFloat(tc.execution_time).toFixed(3) + "s") : "";

      html += '<div class="ce-tc-row' + (tc.passed ? " ce-tc-pass-row" : " ce-tc-fail-row") + '">';
      html += '<div class="ce-tc-header">' + icon + ' <span class="ce-tc-label">Case #' + (idx + 1) + '</span>';
      html += '<span class="ce-tc-status">' + statusLabel + timeStr + '</span>';
      if (tc.is_hidden) {
        html += ' <span class="ce-tc-hidden-badge">hidden</span>';
      }
      html += '</div>';

      // Show I/O only for non-hidden, non-null values
      if (!tc.is_hidden && tc.input !== null && tc.input !== undefined) {
        html += '<div class="ce-tc-io-grid">';
        html += '<div class="ce-tc-io-col"><span class="ce-io-label">Input</span><pre class="ce-tc-pre">' + escHtml(String(tc.input)) + '</pre></div>';
        if (tc.expected_output !== null && tc.expected_output !== undefined) {
          html += '<div class="ce-tc-io-col"><span class="ce-io-label">Expected</span><pre class="ce-tc-pre">' + escHtml(String(tc.expected_output)) + '</pre></div>';
        }
        if (tc.actual_output !== null && tc.actual_output !== undefined) {
          html += '<div class="ce-tc-io-col"><span class="ce-io-label">Your Output</span><pre class="ce-tc-pre">' + escHtml(String(tc.actual_output)) + '</pre></div>';
        }
        html += '</div>';
      }

      if (tc.error_message) {
        html += '<div class="ce-tc-error">' + escHtml(tc.error_message) + '</div>';
      }

      html += '</div>';
    });
    return html;
  }

  function showCompileError(container, msg) {
    if (!msg) { return; }
    container.insertAdjacentHTML(
      "afterbegin",
      '<div class="ce-compile-error"><strong>Compilation Error:</strong><pre>' +
        escHtml(msg) + '</pre></div>'
    );
  }

  /* ------------------------------------------------------------------ *
   * 12. Run button                                                     *
   * ------------------------------------------------------------------ */
  var runUrl    = runtime.handlerUrl(element, "run_code");
  var submitUrl = runtime.handlerUrl(element, "submit_code");

  function setButtonsBusy(busy) {
    if (runBtn)    { runBtn.disabled    = busy; }
    if (submitBtn) { submitBtn.disabled = busy || (maxAttempts > 0 && currentAttempts >= maxAttempts); }
  }

  runBtn.addEventListener("click", function () {
    var code = view.state.doc.toString();
    var lang = currentLang;

    setButtonsBusy(true);
    runBtn.textContent = "Running\u2026";
    runMsg.textContent = "";
    runPanel.classList.remove("visible");
    runResultsBody.innerHTML = "";

    fetch(runUrl, {
      method  : "POST",
      headers : { "Content-Type": "application/json" },
      body    : JSON.stringify({ language: lang, code: code }),
    })
    .then(function (r) { return r.json(); })
    .then(function (result) {
      runBtn.textContent = "\u25B6 Run";
      setButtonsBusy(false);

      if (result.error) {
        runResultsBody.innerHTML = '<div class="ce-error-box">' + escHtml(result.error) + '</div>';
        runPanel.classList.add("visible");
        return;
      }

      showCompileError(runResultsBody, result.compilation_error);
      runResultsBody.innerHTML += buildTestResultRows(result.results);

      var passed = result.passed_count || 0;
      var total  = result.total_count  || 0;
      runMsg.textContent = passed + "/" + total + " sample tests passed";
      runPanel.classList.add("visible");
    })
    .catch(function (err) {
      runBtn.textContent = "\u25B6 Run";
      setButtonsBusy(false);
      runResultsBody.innerHTML = '<div class="ce-error-box">Network error: ' + escHtml(err.message) + '</div>';
      runPanel.classList.add("visible");
      console.error("[CodingExamXBlock] run_code fetch error:", err);
    });
  });

  /* ------------------------------------------------------------------ *
   * 13. Submit button with confirmation dialog                         *
   * ------------------------------------------------------------------ */
  submitBtn.addEventListener("click", function () {
    // Check client-side attempt limit before showing dialog
    if (maxAttempts > 0 && currentAttempts >= maxAttempts) {
      runMsg.textContent = "Attempt limit reached.";
      return;
    }

    var attLeft = maxAttempts > 0
      ? (maxAttempts - currentAttempts) + " attempt(s) remaining."
      : "";
    var confirmMsg = "Submit your code for grading?" +
      (attLeft ? "\n" + attLeft : "") +
      "\n\nYou cannot undo a submission.";

    if (!window.confirm(confirmMsg)) { return; }

    var code = view.state.doc.toString();
    var lang = currentLang;

    setButtonsBusy(true);
    submitBtn.textContent = "Submitting\u2026";
    runMsg.textContent = "";
    submitPanel.classList.remove("visible");
    submitScoreSummary.innerHTML = "";
    submitResultsBody.innerHTML = "";

    fetch(submitUrl, {
      method  : "POST",
      headers : { "Content-Type": "application/json" },
      body    : JSON.stringify({ language: lang, code: code }),
    })
    .then(function (r) { return r.json(); })
    .then(function (result) {
      submitBtn.textContent = "\u2713 Submit";
      setButtonsBusy(false);

      if (result.error) {
        submitResultsBody.innerHTML = '<div class="ce-error-box">' + escHtml(result.error) + '</div>';
        submitPanel.classList.add("visible");
        return;
      }

      // Update attempt counter from server response
      currentAttempts = parseInt(result.attempts || currentAttempts + 1, 10);
      maxAttempts = parseInt(result.max_attempts !== undefined ? result.max_attempts : maxAttempts, 10);
      updateAttemptsDisplay();

      var passed    = result.passed_count || 0;
      var total     = result.total_count  || 0;
      var score     = typeof result.score === "number" ? result.score : null;
      var maxPoints = typeof result.max_points === "number" ? result.max_points : float(initData.points || 10.0);

      submitScoreSummary.innerHTML = buildScoreSummaryHTML(passed, total, score, maxPoints);
      showCompileError(submitResultsBody, result.compilation_error);
      submitResultsBody.innerHTML += buildTestResultRows(result.results);
      submitPanel.classList.add("visible");
    })
    .catch(function (err) {
      submitBtn.textContent = "\u2713 Submit";
      setButtonsBusy(false);
      submitResultsBody.innerHTML = '<div class="ce-error-box">Network error: ' + escHtml(err.message) + '</div>';
      submitPanel.classList.add("visible");
      console.error("[CodingExamXBlock] submit_code fetch error:", err);
    });
  });
}
