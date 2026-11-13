"""
Coding Exam XBlock — Day 3: editor, language switcher, draft save, Run trigger.

Student view serves a CodeMirror 6 editor.  Per-language drafts are persisted
in Scope.user_state.  The run_code handler delegates execution to Teerth's
Judge0Client; student code never runs on the LMS server.
"""
import json
import pkg_resources

from web_fragments.fragment import Fragment
from xblock.core import XBlock
from xblock.fields import Dict, Scope, String

from .runner import Judge0Client

# Languages accepted by both the UI and Teerth's execution client.
SUPPORTED_LANGUAGES = {"python", "java", "cpp"}

# Hard cap to prevent oversized payloads reaching Judge0.
MAX_CODE_SIZE = 50_000  # characters


class CodingExamXBlock(XBlock):
    """XBlock for coding exams with an in-browser CodeMirror 6 editor."""

    # ------------------------------------------------------------------ #
    # Fields — course-author settings                                     #
    # ------------------------------------------------------------------ #

    display_name = String(
        display_name="Display Name",
        default="Coding Exam",
        scope=Scope.settings,
        help="The name shown to students and in Studio.",
    )

    # ------------------------------------------------------------------ #
    # Fields — per-student state                                          #
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
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def resource_string(self, path):
        """Return the contents of a file inside this package as a str."""
        return pkg_resources.resource_string(__name__, path).decode("utf-8")

    def render_template(self, template_name, **kwargs):
        """
        Load an HTML template from coding_exam/templates/ and substitute
        [[KEY]] markers with the provided keyword arguments.
        """
        tpl = self.resource_string(f"templates/{template_name}")
        for key, val in kwargs.items():
            tpl = tpl.replace(f"[[{key}]]", str(val))
        return tpl

    # ------------------------------------------------------------------ #
    # Views                                                               #
    # ------------------------------------------------------------------ #

    def student_view(self, context=None):
        """
        Main student-facing view.
        Serves the editor HTML and attaches CSS + JS resources.
        Initial state (selected language + all saved drafts) is embedded as
        JSON inside the HTML so the JS can restore the editor on page load.
        """
        lang = self.selected_language or "python"
        all_drafts = dict(self.drafts or {})

        # Serialise init data as JSON; the template embeds it verbatim.
        init_json = json.dumps({"language": lang, "drafts": all_drafts})

        html = self.render_template("student_view.html", INIT_DATA=init_json)

        frag = Fragment(html)
        # CSS first so the editor container is styled before CM mounts.
        frag.add_css(self.resource_string("static/css/coding_exam.css"))
        # Vendor bundle defines window.CM; must load before coding_exam.js.
        frag.add_javascript(
            self.resource_string("static/js/vendor/codemirror.bundle.js")
        )
        frag.add_javascript(self.resource_string("static/js/coding_exam.js"))
        # Tells the LMS runtime to call CodingExamXBlock(runtime, element).
        frag.initialize_js("CodingExamXBlock")
        return frag

    def studio_view(self, context=None):
        """Studio editor view — settings authoring comes in a later day."""
        html = self.resource_string("templates/studio_view.html")
        return Fragment(html)

    # ------------------------------------------------------------------ #
    # Handlers                                                            #
    # ------------------------------------------------------------------ #

    @XBlock.json_handler
    def save_draft(self, data, suffix=""):
        """
        Persist the student's draft code for one language.

        Expected payload: { "language": "python"|"java"|"cpp", "code": "<src>" }
        Returns:          { "status": "saved" }  or  { "error": "<msg>" }
        """
        language = data.get("language", "")
        code     = data.get("code", "")

        if language not in SUPPORTED_LANGUAGES:
            return {"error": f"Unsupported language: {language!r}"}
        if not isinstance(code, str):
            return {"error": "code must be a string"}
        if len(code) > MAX_CODE_SIZE:
            return {"error": f"Code exceeds the {MAX_CODE_SIZE}-character limit"}

        # Persist language choice.
        self.selected_language = language

        # Replace the dict (never mutate the default in-place).
        new_drafts = dict(self.drafts or {})
        new_drafts[language] = code
        self.drafts = new_drafts

        return {"status": "saved"}

    @XBlock.json_handler
    def run_code(self, data, suffix=""):
        """
        Execute the student's code via Teerth's Judge0Client and return
        the raw ExecutionResult as a dict.

        Expected payload: { "language": "python"|"java"|"cpp", "code": "<src>" }
        Returns:          ExecutionResult.to_dict() — see runner/client.py.
        """
        language = data.get("language", "")
        code     = data.get("code", "")

        if language not in SUPPORTED_LANGUAGES:
            return {"error": f"Unsupported language: {language!r}"}
        if not isinstance(code, str) or not code.strip():
            return {"error": "No code to run"}
        if len(code) > MAX_CODE_SIZE:
            return {"error": f"Code exceeds the {MAX_CODE_SIZE}-character limit"}

        try:
            client = Judge0Client()
            result = client.execute(source_code=code, language=language)
            return result.to_dict()
        except Exception as exc:                       # pragma: no cover
            # Catch unexpected errors so the LMS never sees a 500.
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
