"""
Test Suite for Day 4: Studio Authoring, Field Validation & Hidden Test Security.
Can be executed standalone on host Python without full Open edX installation.
"""
import copy
import json
import os
import sys

# ------------------------------------------------------------------ #
# Mock XBlock & web_fragments for host-side testing                  #
# ------------------------------------------------------------------ #
class MockScope:
    content = "content"
    settings = "settings"
    user_state = "user_state"
    user_state_summary = "user_state_summary"


class MockField:
    def __init__(self, display_name="", default=None, scope=None, help=""):
        self.display_name = display_name
        self.default = default
        self.scope = scope
        self.help = help
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if self.name in instance.__dict__:
            return instance.__dict__[self.name]
        if callable(self.default):
            val = self.default()
        elif isinstance(self.default, (list, dict)):
            val = copy.deepcopy(self.default)
        else:
            val = self.default
        instance.__dict__[self.name] = val
        return val

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value


class MockFragment:
    def __init__(self, content=""):
        self.content = content
        self.css = []
        self.js = []
        self.init_js = None

    def add_css(self, css_text):
        self.css.append(css_text)

    def add_javascript(self, js_text):
        self.js.append(js_text)

    def initialize_js(self, fn_name):
        self.init_js = fn_name

    def body_html(self):
        return self.content


class MockXBlock:
    @staticmethod
    def json_handler(func):
        func._is_json_handler = True
        return func


# Install mocks into sys.modules
import types

xblock_mod = types.ModuleType("xblock")
xblock_core_mod = types.ModuleType("xblock.core")
xblock_fields_mod = types.ModuleType("xblock.fields")
web_frag_mod = types.ModuleType("web_fragments")
web_frag_frag_mod = types.ModuleType("web_fragments.fragment")

xblock_core_mod.XBlock = MockXBlock
xblock_fields_mod.Scope = MockScope
xblock_fields_mod.String = MockField
xblock_fields_mod.Float = MockField
xblock_fields_mod.Integer = MockField
xblock_fields_mod.Boolean = MockField
xblock_fields_mod.List = MockField
xblock_fields_mod.Dict = MockField
web_frag_frag_mod.Fragment = MockFragment

sys.modules["xblock"] = xblock_mod
sys.modules["xblock.core"] = xblock_core_mod
sys.modules["xblock.fields"] = xblock_fields_mod
sys.modules["web_fragments"] = web_frag_mod
sys.modules["web_fragments.fragment"] = web_frag_frag_mod

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from coding_exam.block import CodingExamXBlock, SUPPORTED_LANGUAGES, DEFAULT_STARTER_CODE


def test_studio_submit_success():
    print("[1/5] Testing studio_submit with valid payload...")
    block = CodingExamXBlock()

    valid_payload = {
        "display_name": "Sum Two Integers",
        "problem_statement": "Read two integers and output their sum.",
        "points": 25.0,
        "allowed_languages": ["python", "cpp"],
        "starter_code": {
            "python": "# Custom py starter\n",
            "cpp": "// Custom cpp starter\n",
        },
        "test_cases": [
            {"input": "1 2\r\n", "expected_output": "3\r\n", "is_hidden": False},
            {"input": "100 200\n", "expected_output": "300\n", "is_hidden": True},
        ],
    }

    res = block.studio_submit(valid_payload)
    assert res == {"result": "success"}, f"Expected success, got {res}"
    assert block.display_name == "Sum Two Integers"
    assert block.problem_statement == "Read two integers and output their sum."
    assert block.points == 25.0
    assert block.allowed_languages == ["python", "cpp"]
    assert block.starter_code["python"] == "# Custom py starter\n"
    assert block.starter_code["cpp"] == "// Custom cpp starter\n"

    # Verify CRLF was normalized to LF
    assert block.test_cases[0]["input"] == "1 2\n"
    assert block.test_cases[0]["expected_output"] == "3\n"
    assert block.test_cases[0]["is_hidden"] is False
    assert block.test_cases[1]["is_hidden"] is True
    print("      ✓ studio_submit persisted valid configuration and normalized line endings")


def test_studio_submit_validation_errors():
    print("[2/5] Testing studio_submit input validation rejects invalid fields...")
    block = CodingExamXBlock()

    base_payload = {
        "display_name": "Valid Title",
        "problem_statement": "Valid Statement",
        "points": 10.0,
        "allowed_languages": ["python"],
        "starter_code": {"python": "code"},
        "test_cases": [{"input": "in", "expected_output": "out", "is_hidden": False}],
    }

    # 1. Empty title
    p = copy.deepcopy(base_payload)
    p["display_name"] = "   "
    assert "error" in block.studio_submit(p)

    # 2. Points <= 0 or not numeric
    p = copy.deepcopy(base_payload)
    p["points"] = 0
    assert "error" in block.studio_submit(p)

    p["points"] = -5.0
    assert "error" in block.studio_submit(p)

    p["points"] = "not_a_number"
    assert "error" in block.studio_submit(p)

    # 3. Allowed languages empty or invalid
    p = copy.deepcopy(base_payload)
    p["allowed_languages"] = []
    assert "error" in block.studio_submit(p)

    p["allowed_languages"] = ["ruby"]
    assert "error" in block.studio_submit(p)

    # 4. Zero test cases
    p = copy.deepcopy(base_payload)
    p["test_cases"] = []
    assert "error" in block.studio_submit(p)

    # 5. All test cases hidden (no visible test case)
    p = copy.deepcopy(base_payload)
    p["test_cases"] = [
        {"input": "in1", "expected_output": "out1", "is_hidden": True},
        {"input": "in2", "expected_output": "out2", "is_hidden": True},
    ]
    res = block.studio_submit(p)
    assert "error" in res
    assert "visible" in res["error"].lower()

    # 6. Exceeding test case IO limits (>10KB)
    p = copy.deepcopy(base_payload)
    p["test_cases"] = [{"input": "A" * 10241, "expected_output": "B", "is_hidden": False}]
    assert "error" in block.studio_submit(p)

    print("      ✓ studio_submit rejects empty titles, invalid points, unknown languages, and all-hidden tests")


def test_hidden_tests_never_exposed_security():
    print("[3/5] Testing SECURITY: hidden test cases are NEVER exposed to student view...")
    block = CodingExamXBlock()

    SECRET_INPUT = "SECRET_INPUT_FOR_EXAM_98765"
    SECRET_OUTPUT = "SECRET_OUTPUT_FOR_EXAM_54321"
    VISIBLE_INPUT = "VISIBLE_SAMPLE_INPUT_111"
    VISIBLE_OUTPUT = "VISIBLE_SAMPLE_OUTPUT_222"

    block.display_name = "Secure Exam Problem"
    block.problem_statement = "Please solve this."
    block.points = 100.0
    block.allowed_languages = ["python"]
    block.test_cases = [
        {"input": VISIBLE_INPUT, "expected_output": VISIBLE_OUTPUT, "is_hidden": False},
        {"input": SECRET_INPUT, "expected_output": SECRET_OUTPUT, "is_hidden": True},
    ]

    frag = block.student_view()
    html_out = frag.body_html()

    # 1. Visible test case must be present in HTML
    assert VISIBLE_INPUT in html_out, "Visible test case input should be rendered in student view"
    assert VISIBLE_OUTPUT in html_out, "Visible test case output should be rendered in student view"

    # 2. Hidden test case must NEVER appear anywhere in the rendered HTML or JSON
    assert SECRET_INPUT not in html_out, "CRITICAL SECURITY BREACH: Secret input leaked in student HTML!"
    assert SECRET_OUTPUT not in html_out, "CRITICAL SECURITY BREACH: Secret output leaked in student HTML!"

    # 3. Verify embedded JSON init data
    import re
    match = re.search(r'<script type="application/json" class="ce-init-data">(.*?)</script>', html_out, re.DOTALL)
    assert match, "ce-init-data script block must be present"
    init_json = json.loads(match.group(1))

    assert "visible_test_cases" in init_json
    assert len(init_json["visible_test_cases"]) == 1
    assert init_json["visible_test_cases"][0]["input"] == VISIBLE_INPUT
    assert SECRET_INPUT not in json.dumps(init_json)
    assert SECRET_OUTPUT not in json.dumps(init_json)
    print("      ✓ Verified: Hidden test inputs/outputs are completely absent from student HTML and JSON")


def test_language_fallback():
    print("[4/5] Testing language fallback when student saved language is disallowed...")
    block = CodingExamXBlock()
    block.allowed_languages = ["java", "cpp"]  # Python is disallowed by instructor
    block.selected_language = "python"        # Student previously saved python draft

    frag = block.student_view()
    html_out = frag.body_html()

    import re
    match = re.search(r'<script type="application/json" class="ce-init-data">(.*?)</script>', html_out, re.DOTALL)
    assert match, "ce-init-data script block must be present"
    init_json = json.loads(match.group(1))

    assert init_json["language"] == "java", f"Expected fallback to 'java', got {init_json['language']}"
    assert init_json["allowed_languages"] == ["java", "cpp"]
    print("      ✓ Language successfully falls back to first allowed language")


def test_studio_view_rendering():
    print("[5/6] Testing studio_view HTML and JSON rendering...")
    block = CodingExamXBlock()
    block.display_name = "Studio Test Problem"
    block.points = 15.0

    frag = block.studio_view()
    html_out = frag.body_html()

    assert "Edit Coding Problem" in html_out
    assert "ce-studio-init-data" in html_out
    assert frag.init_js == "CodingExamStudioXBlock"
    print("      ✓ studio_view initializes CodingExamStudioXBlock and embeds author settings")


def test_disallowed_language_handlers():
    print("[6/6] Testing save_draft & run_code reject disallowed languages...")
    block = CodingExamXBlock()
    block.allowed_languages = ["python"]

    # Try to save draft for C++ when only Python is allowed
    save_res = block.save_draft({"language": "cpp", "code": "int main() {}"})
    assert "error" in save_res
    assert "not allowed" in save_res["error"]

    # Try to run C++ when only Python is allowed
    run_res = block.run_code({"language": "cpp", "code": "int main() {}"})
    assert "error" in run_res
    assert "not allowed" in run_res["error"]
    print("      ✓ Handlers strictly enforce instructor allowed_languages")


if __name__ == "__main__":
    print("===================================================================")
    print("            DAY 4 STUDIO AUTHORING & SECURITY SUITE                ")
    print("===================================================================")
    test_studio_submit_success()
    test_studio_submit_validation_errors()
    test_hidden_tests_never_exposed_security()
    test_language_fallback()
    test_studio_view_rendering()
    test_disallowed_language_handlers()
    print("===================================================================")
    print("                   ALL DAY 4 TESTS PASSED!                         ")
    print("===================================================================")

