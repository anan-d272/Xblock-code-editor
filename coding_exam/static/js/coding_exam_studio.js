/**
 * CodingExamStudioXBlock — Studio authoring JavaScript initialization.
 *
 * Implements standard Open edX Studio lifecycle:
 * - runtime.notify('save', {state: 'start'})
 * - runtime.notify('save', {state: 'end'}) on success
 * - runtime.notify('error', {message: '...'}) on error
 * - runtime.notify('cancel', {}) on cancel
 */
function CodingExamStudioXBlock(runtime, element) {
  "use strict";

  // ------------------------------------------------------------------ //
  // 1. Scoped DOM selectors                                             //
  // ------------------------------------------------------------------ //
  var titleInput     = element.querySelector(".ce-studio-title");
  var stmtTextarea   = element.querySelector(".ce-studio-statement");
  var pointsInput    = element.querySelector(".ce-studio-points");
  var langCheckboxes = element.querySelectorAll(".ce-lang-cb");
  var tabButtons     = element.querySelectorAll(".ce-tab-btn");
  var starterPanes   = element.querySelectorAll(".ce-starter-pane");
  var tcListEl       = element.querySelector(".ce-test-cases-list");
  var addTcBtn       = element.querySelector(".ce-add-tc-btn");
  var saveBtn        = element.querySelector(".ce-studio-save-btn");
  var cancelBtn      = element.querySelector(".ce-studio-cancel-btn");
  var errorBanner    = element.querySelector(".ce-studio-error");

  // ------------------------------------------------------------------ //
  // 2. Parse initial data                                               //
  // ------------------------------------------------------------------ //
  var initData = {
    display_name: "Coding Problem",
    problem_statement: "",
    points: 10.0,
    allowed_languages: ["python"],
    starter_code: {},
    test_cases: [{ input: "", expected_output: "", is_hidden: false }],
  };

  try {
    var rawInit = element.querySelector(".ce-studio-init-data");
    if (rawInit && rawInit.textContent) {
      initData = JSON.parse(rawInit.textContent);
    }
  } catch (err) {
    console.warn("[CodingExamStudioXBlock] Failed to parse init data:", err);
  }

  // Populate base fields
  titleInput.value = initData.display_name || "Coding Problem";
  stmtTextarea.value = initData.problem_statement || "";
  pointsInput.value = (initData.points !== undefined) ? initData.points : 10.0;

  // Populate allowed languages
  var allowedSet = new Set(initData.allowed_languages || ["python"]);
  langCheckboxes.forEach(function (cb) {
    cb.checked = allowedSet.has(cb.value);
  });

  // Populate starter code textareas
  var starters = initData.starter_code || {};
  var pyStarter = element.querySelector(".ce-starter-python");
  var javaStarter = element.querySelector(".ce-starter-java");
  var cppStarter = element.querySelector(".ce-starter-cpp");

  if (pyStarter)   { pyStarter.value   = starters.python || ""; }
  if (javaStarter) { javaStarter.value = starters.java   || ""; }
  if (cppStarter)  { cppStarter.value  = starters.cpp    || ""; }

  // ------------------------------------------------------------------ //
  // 3. Starter code tabs                                                //
  // ------------------------------------------------------------------ //
  tabButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var tabName = btn.getAttribute("data-tab");
      tabButtons.forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");

      starterPanes.forEach(function (pane) {
        if (pane.getAttribute("data-pane") === tabName) {
          pane.style.display = "block";
        } else {
          pane.style.display = "none";
        }
      });
    });
  });

  // ------------------------------------------------------------------ //
  // 4. Test Cases Management                                            //
  // ------------------------------------------------------------------ //
  function createTestCaseRow(tcData, index) {
    var row = document.createElement("div");
    row.className = "ce-tc-row";

    var inVal = (tcData && tcData.input !== undefined) ? tcData.input : "";
    var outVal = (tcData && tcData.expected_output !== undefined) ? tcData.expected_output : "";
    var isHidden = Boolean(tcData && tcData.is_hidden);

    row.innerHTML = [
      '<div class="ce-tc-row-header">',
      '  <span class="ce-tc-badge">Test Case #' + index + "</span>",
      '  <div class="ce-tc-controls">',
      '    <label class="ce-hidden-label">',
      '      <input type="checkbox" class="ce-tc-hidden-cb"' + (isHidden ? " checked" : "") + " />",
      "      Hidden test (masked from students)",
      "    </label>",
      '    <button type="button" class="ce-btn ce-btn-danger ce-remove-tc-btn" title="Remove Test Case">&times; Remove</button>',
      "  </div>",
      "</div>",
      '<div class="ce-tc-fields">',
      '  <div class="ce-tc-col">',
      '    <label class="ce-tc-label">Input (stdin):</label>',
      '    <textarea class="ce-form-control ce-code-textarea ce-tc-input" rows="3" placeholder="Input sent to program stdin..."></textarea>',
      "  </div>",
      '  <div class="ce-tc-col">',
      '    <label class="ce-tc-label">Expected Output (stdout):</label>',
      '    <textarea class="ce-form-control ce-code-textarea ce-tc-output" rows="3" placeholder="Expected program output..."></textarea>',
      "  </div>",
      "</div>",
    ].join("");

    row.querySelector(".ce-tc-input").value = inVal;
    row.querySelector(".ce-tc-output").value = outVal;

    row.querySelector(".ce-remove-tc-btn").addEventListener("click", function () {
      if (tcListEl.children.length <= 1) {
        showError("At least one test case must remain.");
        return;
      }
      row.remove();
      renumberTestCases();
    });

    return row;
  }

  function renumberTestCases() {
    var rows = tcListEl.querySelectorAll(".ce-tc-row");
    rows.forEach(function (r, idx) {
      var badge = r.querySelector(".ce-tc-badge");
      if (badge) {
        badge.textContent = "Test Case #" + (idx + 1);
      }
    });
  }

  // Populate initial test cases
  tcListEl.innerHTML = "";
  var initialCases = initData.test_cases || [];
  if (initialCases.length === 0) {
    initialCases = [{ input: "", expected_output: "", is_hidden: false }];
  }
  initialCases.forEach(function (tc, idx) {
    tcListEl.appendChild(createTestCaseRow(tc, idx + 1));
  });

  // Add Test Case button handler
  addTcBtn.addEventListener("click", function () {
    if (tcListEl.children.length >= 50) {
      showError("Maximum limit of 50 test cases reached.");
      return;
    }
    clearError();
    var nextIndex = tcListEl.children.length + 1;
    tcListEl.appendChild(createTestCaseRow({ input: "", expected_output: "", is_hidden: false }, nextIndex));
  });

  // ------------------------------------------------------------------ //
  // 5. Error messaging helpers                                          //
  // ------------------------------------------------------------------ //
  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.style.display = "block";
    errorBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function clearError() {
    errorBanner.textContent = "";
    errorBanner.style.display = "none";
  }

  // ------------------------------------------------------------------ //
  // 6. Save & Cancel Handlers                                           //
  // ------------------------------------------------------------------ //
  var submitUrl = runtime.handlerUrl(element, "studio_submit");

  saveBtn.addEventListener("click", function () {
    clearError();

    // Collect Title
    var title = titleInput.value.trim();
    if (!title) {
      showError("Problem title cannot be empty.");
      return;
    }

    // Collect Points
    var points = parseFloat(pointsInput.value);
    if (isNaN(points) || points <= 0) {
      showError("Points must be a positive number greater than 0.");
      return;
    }

    // Collect Allowed Languages
    var selectedLangs = [];
    langCheckboxes.forEach(function (cb) {
      if (cb.checked) {
        selectedLangs.push(cb.value);
      }
    });
    if (selectedLangs.length === 0) {
      showError("At least one programming language must be selected.");
      return;
    }

    // Collect Starter Code
    var starterPayload = {
      python: pyStarter ? pyStarter.value : "",
      java: javaStarter ? javaStarter.value : "",
      cpp: cppStarter ? cppStarter.value : "",
    };

    // Collect Test Cases
    var tcRows = tcListEl.querySelectorAll(".ce-tc-row");
    if (tcRows.length === 0) {
      showError("At least 1 test case is required.");
      return;
    }

    var testCasesPayload = [];
    var hasVisible = false;

    tcRows.forEach(function (row) {
      var inVal = row.querySelector(".ce-tc-input").value;
      var outVal = row.querySelector(".ce-tc-output").value;
      var isHidden = row.querySelector(".ce-tc-hidden-cb").checked;
      if (!isHidden) {
        hasVisible = true;
      }
      testCasesPayload.push({
        input: inVal,
        expected_output: outVal,
        is_hidden: isHidden,
      });
    });

    if (!hasVisible) {
      showError("At least 1 visible (non-hidden) test case is required.");
      return;
    }

    var payload = {
      display_name: title,
      problem_statement: stmtTextarea.value,
      points: points,
      allowed_languages: selectedLangs,
      starter_code: starterPayload,
      test_cases: testCasesPayload,
    };

    // Notify runtime that save is in progress
    runtime.notify("save", { state: "start" });

    fetch(submitUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (data.error) {
          showError(data.error);
          runtime.notify("error", { message: data.error });
        } else {
          clearError();
          runtime.notify("save", { state: "end" });
        }
      })
      .catch(function (err) {
        var msg = "Network error while saving: " + err.message;
        showError(msg);
        runtime.notify("error", { message: msg });
      });
  });

  cancelBtn.addEventListener("click", function () {
    runtime.notify("cancel", {});
  });
}

