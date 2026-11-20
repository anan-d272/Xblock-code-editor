"""
Day 5 Unit Tests — Run and Submit End-to-End, Scoring, and Attempt Limits.

Tests:
  1. Scoring: 0 passed → score 0
  2. Scoring: partial pass → proportional score
  3. Scoring: all passed → full score
  4. Scoring: edge case total==0 → score 0
  5. Attempt limit: third submit after max_attempts=2 is rejected
  6. Attempt is NOT incremented on runner failure
  7. Runner failure clears in-progress flag
  8. submit_in_progress guard rejects concurrent submissions
  9. Hidden test I/O stripped before browser response (submit)
 10. max_attempts=0 means unlimited (submit always allowed)
 11. run_code never modifies attempts or score
"""

import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class _Scope:
    settings   = "settings"
    user_state = "user_state"


class _FieldDescriptor:
    def __init__(self, default):
        self._default = default
        self._attr    = None

    def __set_name__(self, owner, name):
        self._attr = "_field_" + name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self._attr, self._default)

    def __set__(self, obj, value):
        setattr(obj, self._attr, value)


def _make_field(default):
    return _FieldDescriptor(default)

def String(default="", **kw):     return _make_field(default)
def Float(default=0.0, **kw):     return _make_field(default)
def Integer(default=0, **kw):     return _make_field(default)
def Boolean(default=False, **kw): return _make_field(default)
def List(default=None, **kw):     return _make_field(default if default is not None else [])
def Dict(default=None, **kw):     return _make_field(default if default is not None else {})

class Scope:
    settings   = _Scope.settings
    user_state = _Scope.user_state

class Fragment:
    def __init__(self, content=""):
        self.content = content
    def add_css(self, _):        pass
    def add_javascript(self, _): pass
    def initialize_js(self, _):  pass

class XBlock:
    @staticmethod
    def json_handler(fn):
        return fn


_MOCK_MODULE_KEYS = [
    "web_fragments", "web_fragments.fragment",
    "xblock", "xblock.core", "xblock.fields",
    "coding_exam", "coding_exam.block", "coding_exam.runner",
]

blk = None  # filled in by setUpModule


def setUpModule():
    """Install lightweight mock stubs so block.py can be imported without Open edX."""
    global blk
    # Remove any stale copies so each test module gets a clean import.
    for key in _MOCK_MODULE_KEYS:
        sys.modules.pop(key, None)

    wf_mod = types.ModuleType("web_fragments")
    wf_frag_mod = types.ModuleType("web_fragments.fragment")
    wf_frag_mod.Fragment = Fragment
    sys.modules["web_fragments"] = wf_mod
    sys.modules["web_fragments.fragment"] = wf_frag_mod

    xblock_mod = types.ModuleType("xblock")
    xblock_core_mod = types.ModuleType("xblock.core")
    xblock_core_mod.XBlock = XBlock
    sys.modules["xblock"] = xblock_mod
    sys.modules["xblock.core"] = xblock_core_mod

    xblock_fields_mod = types.ModuleType("xblock.fields")
    xblock_fields_mod.String  = String
    xblock_fields_mod.Float   = Float
    xblock_fields_mod.Integer = Integer
    xblock_fields_mod.Boolean = Boolean
    xblock_fields_mod.List    = List
    xblock_fields_mod.Dict    = Dict
    xblock_fields_mod.Scope   = Scope
    sys.modules["xblock.fields"] = xblock_fields_mod

    import importlib
    import coding_exam.block
    importlib.reload(coding_exam.block)
    blk = coding_exam.block


def tearDownModule():
    """Remove mock stubs so subsequent test modules start clean."""
    for key in _MOCK_MODULE_KEYS:
        sys.modules.pop(key, None)


def _make_block(
    points=10.0,
    max_attempts=0,
    test_cases=None,
    attempts=0,
    score=None,
    submission_in_progress=False,
):
    if test_cases is None:
        test_cases = [
            {"input": "1\n", "expected_output": "1\n", "is_hidden": False},
            {"input": "2\n", "expected_output": "2\n", "is_hidden": True},
        ]

    runtime = MagicMock()
    b = blk.CodingExamXBlock.__new__(blk.CodingExamXBlock)
    b.runtime              = runtime
    b.display_name         = "Test Problem"
    b.problem_statement    = ""
    b.points               = points
    b.max_attempts         = max_attempts
    b.allowed_languages    = ["python"]
    b.starter_code         = {}
    b.test_cases           = test_cases
    b.selected_language    = "python"
    b.drafts               = {}
    b.attempts             = attempts
    b.submission_in_progress = submission_in_progress
    b.score                = score
    b.last_submission      = {}
    b.last_run_results     = {}
    return b


def _run_submission_success(passed, total, max_points=10.0, hidden_in_results=False):
    score = (passed / total * max_points) if total > 0 else 0.0
    results = []
    for i in range(passed):
        results.append({
            "test_case_id": i + 1,
            "passed": True,
            "is_hidden": hidden_in_results and (i % 2 == 1),
            "input": "x\n" if not (hidden_in_results and i % 2 == 1) else "SECRET",
            "expected_output": "x\n" if not (hidden_in_results and i % 2 == 1) else "SECRET",
            "actual_output": "x\n" if not (hidden_in_results and i % 2 == 1) else "SECRET",
            "status": "PASSED",
            "error_message": "",
            "execution_time": 0.1,
        })
    for i in range(total - passed):
        results.append({
            "test_case_id": passed + i + 1,
            "passed": False,
            "is_hidden": hidden_in_results,
            "input": "y\n" if not hidden_in_results else "SECRET",
            "expected_output": "y\n" if not hidden_in_results else "SECRET",
            "actual_output": "z\n" if not hidden_in_results else "SECRET",
            "status": "WRONG_ANSWER",
            "error_message": "",
            "execution_time": 0.1,
        })
    return {
        "status": "success",
        "action": "submit",
        "language": "python",
        "score": score,
        "max_points": max_points,
        "percentage": (passed / total * 100) if total > 0 else 0.0,
        "passed_count": passed,
        "total_count": total,
        "feedback": f"{passed}/{total} passed",
        "compilation_error": None,
        "results": results,
    }


class TestScoring(unittest.TestCase):

    def _submit(self, block, passed, total, max_points=10.0):
        with patch.object(blk, "run_submission",
                          return_value=_run_submission_success(passed, total, max_points)):
            with patch.object(blk, "Judge0Client", return_value=MagicMock()):
                return block.submit_code({"language": "python", "code": "print(1)"})

    def test_score_zero_when_no_tests_pass(self):
        b = _make_block(points=10.0)
        result = self._submit(b, passed=0, total=2)
        self.assertNotIn("error", result)
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(b.score, 0.0)

    def test_score_proportional_for_partial_pass(self):
        b = _make_block(points=10.0)
        result = self._submit(b, passed=1, total=2)
        self.assertAlmostEqual(result["score"], 5.0, places=5)
        self.assertAlmostEqual(b.score, 5.0, places=5)

    def test_score_full_when_all_pass(self):
        b = _make_block(points=10.0)
        result = self._submit(b, passed=3, total=3)
        self.assertAlmostEqual(result["score"], 10.0, places=5)

    def test_score_zero_when_total_is_zero(self):
        b = _make_block(points=10.0)
        result = self._submit(b, passed=0, total=0)
        self.assertEqual(result.get("score", 0), 0.0)


class TestAttemptLimit(unittest.TestCase):

    def _submit(self, block):
        with patch.object(blk, "run_submission",
                          return_value=_run_submission_success(1, 1)):
            with patch.object(blk, "Judge0Client", return_value=MagicMock()):
                return block.submit_code({"language": "python", "code": "print(1)"})

    def test_first_two_submits_accepted_then_third_rejected(self):
        b = _make_block(max_attempts=2)
        r1 = self._submit(b)
        self.assertNotIn("error", r1)
        self.assertEqual(b.attempts, 1)

        r2 = self._submit(b)
        self.assertNotIn("error", r2)
        self.assertEqual(b.attempts, 2)

        r3 = self._submit(b)
        self.assertIn("error", r3)
        self.assertIn("limit", r3["error"].lower())
        self.assertEqual(b.attempts, 2)

    def test_unlimited_when_max_attempts_zero(self):
        b = _make_block(max_attempts=0)
        for _ in range(5):
            r = self._submit(b)
            self.assertNotIn("error", r)
        self.assertEqual(b.attempts, 5)


class TestRunnerFailure(unittest.TestCase):

    def test_runner_exception_does_not_consume_attempt(self):
        b = _make_block(max_attempts=0, attempts=0)
        with patch.object(blk, "run_submission", side_effect=RuntimeError("conn failed")):
            with patch.object(blk, "Judge0Client", return_value=MagicMock()):
                result = b.submit_code({"language": "python", "code": "print(1)"})
        self.assertIn("error", result)
        self.assertEqual(b.attempts, 0)
        b.runtime.publish.assert_not_called()

    def test_runner_failure_clears_in_progress_flag(self):
        b = _make_block()
        with patch.object(blk, "run_submission", side_effect=RuntimeError("timeout")):
            with patch.object(blk, "Judge0Client", return_value=MagicMock()):
                b.submit_code({"language": "python", "code": "print(1)"})
        self.assertFalse(b.submission_in_progress)


class TestSubmissionInProgressGuard(unittest.TestCase):

    def test_concurrent_submission_is_rejected(self):
        b = _make_block(submission_in_progress=True)
        result = b.submit_code({"language": "python", "code": "print(1)"})
        self.assertIn("error", result)
        self.assertIn("progress", result["error"].lower())


class TestHiddenTestSecurity(unittest.TestCase):

    def test_hidden_io_stripped_from_submit_response(self):
        b = _make_block(points=10.0)
        fake_result = _run_submission_success(passed=2, total=4, hidden_in_results=True)
        for tc in fake_result["results"]:
            if tc.get("is_hidden"):
                tc["input"]           = "HIDDEN_SECRET_INPUT"
                tc["expected_output"] = "HIDDEN_SECRET_OUTPUT"
                tc["actual_output"]   = "HIDDEN_SECRET_ACTUAL"

        with patch.object(blk, "run_submission", return_value=fake_result):
            with patch.object(blk, "Judge0Client", return_value=MagicMock()):
                response = b.submit_code({"language": "python", "code": "print(1)"})

        for tc in response.get("results", []):
            if tc.get("is_hidden"):
                self.assertIsNone(tc.get("input"))
                self.assertIsNone(tc.get("expected_output"))
                self.assertIsNone(tc.get("actual_output"))


class TestRunCodeNoSideEffects(unittest.TestCase):

    def test_run_code_does_not_modify_attempts_or_score(self):
        b = _make_block(attempts=3, score=7.0)
        fake_result = _run_submission_success(1, 1)
        fake_result["action"] = "run"
        with patch.object(blk, "run_submission", return_value=fake_result):
            with patch.object(blk, "Judge0Client", return_value=MagicMock()):
                b.run_code({"language": "python", "code": "print(1)"})
        self.assertEqual(b.attempts, 3)
        self.assertEqual(b.score, 7.0)
        b.runtime.publish.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
