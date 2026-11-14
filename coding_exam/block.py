"""
Coding Exam XBlock — Day 4: Problem Authoring & Settings.

Allows instructors to create coding problems with:
- Display name and problem statement
- Points (grading weight)
- Allowed programming languages (subset of python, java, cpp)
- Per-language starter code templates
- Visible and hidden test cases

Student code never runs on the LMS/CMS server; all execution is handled by
Teerth's execution client and test case runner.
"""
import html
import json
import math
import pkg_resources

from web_fragments.fragment import Fragment
from xblock.core import XBlock
from xblock.fields import Dict, Float, List, Scope, String

from .runner import Judge0Client, run_submission

# Languages supported by the execution runner.
SUPPORTED_LANGUAGES = ("python", "java", "cpp")

# Validation limits
MAX_CODE_SIZE = 50_000          # 50k characters
MAX_TITLE_LENGTH = 255          # 255 characters
MAX_STATEMENT_LENGTH = 50_000   # 50k characters
MAX_TEST_CASES = 50             # Up to 50 test cases per problem
MAX_TEST_CASE_IO_SIZE = 10_240  # 10 KB per input/output

# Default starter code templates
DEFAULT_STARTER_CODE = {
    "python": (
        "# Write your Python solution here\n\n"
        "def main():\n"
        "    pass  # TODO: implement\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    ),
    "java": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        // TODO: implement\n"
        "    }\n"
        "}\n"
    ),
    "cpp": (
        "#include <iostream>\n"
        "using namespace std;\n\n"
        "int main() {\n"
        "    // TODO: implement\n"
        "    return 0;\n"
        "}\n"
    ),
}

# Default sample test case
DEFAULT_TEST_CASES = [
    {
        "input": "10\n20\n",
        "expected_output": "30\n",
        "is_hidden": False,
    }
]


class CodingExamXBlock(XBlock):
    """XBlock for coding problems with an in-browser CodeMirror editor and Studio authoring."""

    # ------------------------------------------------------------------ #
    # Fields — Instructor / Course Author Settings (Scope.settings)       #
    # ------------------------------------------------------------------ #

    display_name = String(
        display_name="Display Name",
        default="Coding Problem",
        scope=Scope.settings,
        help="The problem title shown to students and in Studio.",
    )

    problem_statement = String(
        display_name="Problem Statement",
        default="",
        scope=Scope.settings,
        help="Problem instructions and description for students.",
    )

    points = Float(
        display_name="Maximum Points",
        default=10.0,
        scope=Scope.settings,
        help="Maximum grade points possible for this problem (must be > 0).",
    )

    allowed_languages = List(
        display_name="Allowed Languages",
        default=["python"],
        scope=Scope.settings,
        help="Programming languages students are permitted to choose from.",
    )

    starter_code = Dict(
        display_name="Starter Code",
        default=DEFAULT_STARTER_CODE,
        scope=Scope.settings,
        help="Per-language starter code templates.",
    )

    test_cases = List(
        display_name="Test Cases",
        default=DEFAULT_TEST_CASES,
        scope=Scope.settings,
        help="List of test cases: [{'input': str, 'expected_output': str, 'is_hidden': bool}].",
    )

    # ------------------------------------------------------------------ #
    # Fields — Per-Student State (Scope.user_state)                       #
    # ------------------------------------------------------------------ #

    selected_language = String(
        default="python",
        scope=Scope.user_state,
        help="The programming language last selected by this student.",
    )

    drafts = Dict(
        default={},
        scope=Scope.user_state,
        help="Per-language draft code, keyed by language name (python/java/cpp).",
    )

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    def resource_string(self, path):
        """Return the contents of a package resource as a string."""
        return pkg_resources.resource_string(__name__, path).decode("utf-8")

    def render_template(self, template_name, **kwargs):
        """
        Load an HTML template from coding_exam/templates/ and substitute
        [[KEY]] markers with kwargs.
        """
        tpl = self.resource_string(f"templates/{template_name}")
        for key, val in kwargs.items():
            tpl = tpl.replace(f"[[{key}]]", str(val))
        return tpl

    def get_effective_allowed_languages(self):
        """Return a validated list of allowed languages, defaulting to ['python']."""
        raw = self.allowed_languages or ["python"]
        valid = [lang for lang in raw if lang in SUPPORTED_LANGUAGES]
        return valid if valid else ["python"]

    def get_effective_starter_code(self):
        """Return starter code dict merged with defaults."""
        current = dict(self.starter_code or {})
        merged = {}
        for lang in SUPPORTED_LANGUAGES:
            merged[lang] = current.get(lang, DEFAULT_STARTER_CODE.get(lang, ""))
        return merged

    # ------------------------------------------------------------------ #
    # Views                                                              #
    # ------------------------------------------------------------------ #

    def student_view(self, context=None):
        """
        Main student-facing view.
        Serves the problem statement, visible sample test cases, editor,
        and action buttons. Hidden test cases are strictly filtered out.
        """
        allowed = self.get_effective_allowed_languages()
        starters = self.get_effective_starter_code()
        all_drafts = dict(self.drafts or {})

        # Ensure student's selected language is among the currently allowed languages
        current_lang = self.selected_language or "python"
        if current_lang not in allowed:
            current_lang = allowed[0]

        # SECURITY: Only extract visible test cases for the browser.
        # Hidden test cases, their inputs, and outputs must NEVER reach the student view.
        raw_test_cases = self.test_cases or DEFAULT_TEST_CASES
        visible_test_cases = []
        for idx, tc in enumerate(raw_test_cases, 1):
            if not tc.get("is_hidden", False):
                visible_test_cases.append({
                    "id": idx,
                    "input": tc.get("input", ""),
                    "expected_output": tc.get("expected_output", ""),
                })

        # Render problem statement HTML safely
        statement_text = self.problem_statement or ""
        escaped_statement = html.escape(statement_text).replace("\n", "<br>")

        # Render visible sample tests HTML
        sample_tests_html = ""
        if visible_test_cases:
            parts = ['<div class="ce-sample-tests"><div class="ce-sample-tests-title">Sample Test Cases</div>']
            for tc in visible_test_cases:
                tc_id = tc["id"]
                tc_in = html.escape(tc["input"]).replace("\n", "<br>")
                tc_out = html.escape(tc["expected_output"]).replace("\n", "<br>")
                parts.append(f"""
                <div class="ce-sample-test-case">
                  <div class="ce-sample-test-label">Sample Case #{tc_id}</div>
                  <div class="ce-sample-test-io">
                    <div class="ce-sample-test-col">
                      <span class="ce-io-label">Input</span>
                      <pre class="ce-io-pre">{tc_in}</pre>
                    </div>
                    <div class="ce-sample-test-col">
                      <span class="ce-io-label">Expected Output</span>
                      <pre class="ce-io-pre">{tc_out}</pre>
                    </div>
                  </div>
                </div>
                """)
            parts.append('</div>')
            sample_tests_html = "".join(parts)

        # JSON state passed to frontend JS
        init_json = json.dumps({
            "language": current_lang,
            "allowed_languages": allowed,
            "starter_code": {lang: starters.get(lang, "") for lang in allowed},
            "drafts": all_drafts,
            "visible_test_cases": visible_test_cases,
            "display_name": self.display_name or "Coding Problem",
            "points": float(self.points or 10.0),
        })

        html_content = self.render_template(
            "student_view.html",
            DISPLAY_NAME=html.escape(self.display_name or "Coding Problem"),
            POINTS=f"{float(self.points or 10.0):.1f}",
            PROBLEM_STATEMENT=escaped_statement,
            HAS_STATEMENT="visible" if statement_text.strip() else "hidden",
            SAMPLE_TESTS=sample_tests_html,
            INIT_DATA=init_json,
        )

        frag = Fragment(html_content)
        frag.add_css(self.resource_string("static/css/coding_exam.css"))
        frag.add_javascript(self.resource_string("static/js/vendor/codemirror.bundle.js"))
        frag.add_javascript(self.resource_string("static/js/coding_exam.js"))
        frag.initialize_js("CodingExamXBlock")
        return frag

    def studio_view(self, context=None):
        """
        Studio authoring view.
        Allows instructors to edit title, problem description, points,
        allowed languages, starter templates, and test cases.
        """
        allowed = self.get_effective_allowed_languages()
        starters = self.get_effective_starter_code()
        raw_test_cases = self.test_cases or DEFAULT_TEST_CASES

        init_json = json.dumps({
            "display_name": self.display_name or "Coding Problem",
            "problem_statement": self.problem_statement or "",
            "points": float(self.points or 10.0),
            "allowed_languages": allowed,
            "starter_code": starters,
            "test_cases": [
                {
                    "input": str(tc.get("input", "")),
                    "expected_output": str(tc.get("expected_output", "")),
                    "is_hidden": bool(tc.get("is_hidden", False)),
                }
                for tc in raw_test_cases
            ],
        })

        html_content = self.render_template("studio_view.html", INIT_DATA=init_json)
        frag = Fragment(html_content)
        frag.add_css(self.resource_string("static/css/coding_exam_studio.css"))
        frag.add_javascript(self.resource_string("static/js/coding_exam_studio.js"))
        frag.initialize_js("CodingExamStudioXBlock")
        return frag

    # ------------------------------------------------------------------ #
    # Handlers                                                           #
    # ------------------------------------------------------------------ #

    @XBlock.json_handler
    def studio_submit(self, data, suffix=""):
        """
        Save handler for Studio authoring form.
        Validates all fields and stores them in Scope.settings.
        """
        # 1. Title validation
        raw_title = data.get("display_name", "")
        if not isinstance(raw_title, str) or not raw_title.strip():
            return {"error": "Problem title cannot be empty."}
        title = raw_title.strip()
        if len(title) > MAX_TITLE_LENGTH:
            return {"error": f"Title exceeds maximum limit of {MAX_TITLE_LENGTH} characters."}

        # 2. Problem Statement validation
        raw_statement = data.get("problem_statement", "")
        if not isinstance(raw_statement, str):
            return {"error": "Problem statement must be text."}
        if len(raw_statement) > MAX_STATEMENT_LENGTH:
            return {"error": f"Problem statement exceeds maximum limit of {MAX_STATEMENT_LENGTH} characters."}

        # 3. Points validation
        raw_points = data.get("points")
        try:
            points_val = float(raw_points)
            if math.isnan(points_val) or math.isinf(points_val) or points_val <= 0:
                return {"error": "Points must be a positive number greater than 0."}
        except (ValueError, TypeError):
            return {"error": "Points must be a valid number."}

        # 4. Allowed Languages validation
        raw_langs = data.get("allowed_languages")
        if not isinstance(raw_langs, list) or not raw_langs:
            return {"error": "At least one programming language must be selected."}
        cleaned_langs = []
        for lang in raw_langs:
            if not isinstance(lang, str):
                return {"error": "Language identifier must be a string."}
            norm_lang = lang.strip().lower()
            if norm_lang not in SUPPORTED_LANGUAGES:
                supported_str = ", ".join(SUPPORTED_LANGUAGES)
                return {"error": f"Unsupported language '{lang}'. Choose from: {supported_str}."}
            if norm_lang not in cleaned_langs:
                cleaned_langs.append(norm_lang)

        # 5. Starter Code validation
        raw_starters = data.get("starter_code", {})
        if not isinstance(raw_starters, dict):
            return {"error": "Starter code must be a dictionary keyed by language."}
        updated_starters = dict(self.starter_code or DEFAULT_STARTER_CODE)
        for lang in cleaned_langs:
            code = raw_starters.get(lang, updated_starters.get(lang, ""))
            if not isinstance(code, str):
                return {"error": f"Starter code for {lang} must be a string."}
            if len(code) > MAX_CODE_SIZE:
                return {"error": f"Starter code for {lang} exceeds {MAX_CODE_SIZE} characters."}
            updated_starters[lang] = code

        # 6. Test Cases validation
        raw_tests = data.get("test_cases")
        if not isinstance(raw_tests, list) or not raw_tests:
            return {"error": "At least 1 test case is required."}
        if len(raw_tests) > MAX_TEST_CASES:
            return {"error": f"Maximum of {MAX_TEST_CASES} test cases allowed per problem."}

        has_visible_case = False
        cleaned_test_cases = []
        for idx, tc in enumerate(raw_tests, 1):
            if not isinstance(tc, dict):
                return {"error": f"Test case #{idx} is malformed."}
            tc_input = str(tc.get("input", ""))
            tc_output = str(tc.get("expected_output", ""))
            is_hidden = bool(tc.get("is_hidden", False))

            if len(tc_input) > MAX_TEST_CASE_IO_SIZE:
                return {"error": f"Test case #{idx} input exceeds {MAX_TEST_CASE_IO_SIZE} bytes limit."}
            if len(tc_output) > MAX_TEST_CASE_IO_SIZE:
                return {"error": f"Test case #{idx} expected output exceeds {MAX_TEST_CASE_IO_SIZE} bytes limit."}

            if not is_hidden:
                has_visible_case = True

            # Normalize line endings to LF
            tc_input = tc_input.replace("\r\n", "\n").replace("\r", "\n")
            tc_output = tc_output.replace("\r\n", "\n").replace("\r", "\n")

            cleaned_test_cases.append({
                "input": tc_input,
                "expected_output": tc_output,
                "is_hidden": is_hidden,
            })

        if not has_visible_case:
            return {"error": "At least 1 visible (non-hidden) test case is required."}

        # Persist valid settings
        self.display_name = title
        self.problem_statement = raw_statement
        self.points = points_val
        self.allowed_languages = cleaned_langs
        self.starter_code = updated_starters
        self.test_cases = cleaned_test_cases

        return {"result": "success"}

    @XBlock.json_handler
    def save_draft(self, data, suffix=""):
        """
        Persist the student's draft code for a specific language.
        Scoped to user_state.
        """
        language = data.get("language", "")
        code = data.get("code", "")

        allowed = self.get_effective_allowed_languages()
        if language not in allowed:
            return {"error": f"Language {language!r} is not allowed for this problem."}
        if not isinstance(code, str):
            return {"error": "Code must be a string."}
        if len(code) > MAX_CODE_SIZE:
            return {"error": f"Code exceeds the {MAX_CODE_SIZE}-character limit."}

        self.selected_language = language
        new_drafts = dict(self.drafts or {})
        new_drafts[language] = code
        self.drafts = new_drafts

        return {"status": "saved"}

    @XBlock.json_handler
    def run_code(self, data, suffix=""):
        """
        Execute student code against visible test cases using Teerth's runner.
        Action 'run' filters out hidden test cases and masks inputs/outputs.
        """
        language = data.get("language", "")
        code = data.get("code", "")

        allowed = self.get_effective_allowed_languages()
        if language not in allowed:
            return {"error": f"Language {language!r} is not allowed for this problem."}
        if not isinstance(code, str) or not code.strip():
            return {"error": "No code to run."}
        if len(code) > MAX_CODE_SIZE:
            return {"error": f"Code exceeds the {MAX_CODE_SIZE}-character limit."}

        try:
            client = Judge0Client()
            # run_submission evaluates visible test cases when action='run'
            result = run_submission(
                client=client,
                source_code=code,
                language=language,
                test_cases_data=self.test_cases or DEFAULT_TEST_CASES,
                action="run",
                max_points=float(self.points or 10.0),
            )
            return result
        except Exception as exc:  # pragma: no cover
            return {
                "status": "INTERNAL_ERROR",
                "is_success": False,
                "stdout": "",
                "stderr": str(exc),
                "compile_output": "",
                "execution_time": 0.0,
                "memory": 0,
                "status_id": 0,
                "status_description": "Internal Error",
                "message": str(exc),
            }
