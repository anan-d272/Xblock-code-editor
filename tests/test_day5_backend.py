"""
Test Suite for Day 5 Backend Development:
End-to-End Run, Submit, Scoring, Open edX Grade Publishing, and Attempt Storage.
"""
import os
import sys
from unittest.mock import MagicMock

# Mock web_fragments / xblock for host-side testing without full Open edX environment
for mod in ["web_fragments", "web_fragments.fragment", "xblock", "xblock.core", "xblock.fields"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from coding_exam.runner import (
    Judge0Client,
    DockerSandboxClient,
    handle_run_request,
    handle_submit_request,
    publish_xblock_grade,
    record_student_attempt,
)


class MockRuntime:
    """Mock Open edX XBlock runtime to capture grade publish events and user context."""
    def __init__(self, user_id="student_teerth_101"):
        self.user_id = user_id
        self.published_events = []

    def publish(self, block, event_type, event_data):
        self.published_events.append({"event_type": event_type, "event_data": event_data})


class MockCodingExamBlock:
    """Mock instance mirroring CodingExamXBlock state and attributes."""
    def __init__(self, max_points=100.0):
        self.max_points = max_points
        self.test_cases = [
            {"id": 1, "input": "10 20\n", "expected_output": "30", "is_hidden": False},
            {"id": 2, "input": "5 -2\n", "expected_output": "3", "is_hidden": False},
            {"id": 3, "input": "100 250\n", "expected_output": "350", "is_hidden": True},
            {"id": 4, "input": "0 0\n", "expected_output": "0", "is_hidden": True},
        ]
        self.attempts = 0
        self.last_submission = {}
        self.submission_history = []
        self.runtime = MockRuntime()
        self.scope_ids = MagicMock(user_id="student_teerth_101")


def test_run_handler_does_not_publish_grade():
    print("[1/5] Testing Run handler executes visible test cases without publishing grades...")
    block = MockCodingExamBlock(max_points=100.0)
    client = Judge0Client()
    code = "a, b = map(int, input().split())\nprint(a + b)"

    res = handle_run_request(block, {"language": "python", "code": code}, client=client)

    # 1. Action is 'run'
    assert res["action"] == "run"
    # 2. Only visible test cases evaluated (2 of 4)
    assert res["total_count"] == 2
    assert res["passed_count"] == 2
    assert res["status"] == "success"
    # 3. CRITICAL: Runtime must NOT have published any grade event
    assert len(block.runtime.published_events) == 0, "Run handler must NOT publish grades to Open edX!"
    # 4. Attempt count must remain 0
    assert block.attempts == 0
    print("      ✓ Run evaluated visible test cases and verified zero grade events published")


def test_submit_handler_publishes_grade_and_stores_attempt():
    print("[2/5] Testing Submit handler evaluates all test cases, publishes grade, and stores attempt...")
    block = MockCodingExamBlock(max_points=100.0)
    client = Judge0Client()
    code = "a, b = map(int, input().split())\nprint(a + b)"

    res = handle_submit_request(block, {"language": "python", "code": code}, client=client)

    # 1. Action is 'submit'
    assert res["action"] == "submit"
    # 2. All test cases evaluated (4 of 4)
    assert res["total_count"] == 4
    assert res["passed_count"] == 4
    assert res["score"] == 100.0
    assert res["percentage"] == 100.0

    # 3. Grade published to Open edX gradebook
    assert len(block.runtime.published_events) == 1
    grade_evt = block.runtime.published_events[0]
    assert grade_evt["event_type"] == "grade"
    assert grade_evt["event_data"]["value"] == 100.0
    assert grade_evt["event_data"]["max_value"] == 100.0

    # 4. Attempt stored
    assert block.attempts == 1
    assert block.last_submission["attempt_number"] == 1
    assert block.last_submission["score"] == 100.0
    assert block.last_submission["user_id"] == "student_teerth_101"
    assert block.last_submission["status"] == "success"
    assert bool(block.last_submission["timestamp"]) is True
    assert len(block.submission_history) == 1

    # 5. Verify hidden test cases are strictly masked in the response
    for r in res["results"]:
        if r["is_hidden"]:
            assert r["input"] == "[Hidden]"
            assert r["expected_output"] == "[Hidden]"
            assert r["actual_output"] == "[Hidden]"

    print("      ✓ Submit evaluated all test cases, published grade to gradebook, and saved attempt")


def test_partial_scoring_and_repeated_submissions():
    print("[3/5] Testing partial scoring and repeated submissions...")
    block = MockCodingExamBlock(max_points=50.0)
    client = Judge0Client()

    # Submission 1: Code passes 2 of 4 test cases (only works for positive numbers < 50)
    code_partial = """
a, b = map(int, input().split())
if a + b < 50:
    print(a + b)
else:
    print(999)
"""
    res1 = handle_submit_request(block, {"language": "python", "code": code_partial}, client=client)
    assert res1["passed_count"] == 3  # passes 10+20=30, 5-2=3, 0+0=0; fails 100+250=350
    assert block.attempts == 1
    # 3/4 * 50.0 = 37.5
    assert block.last_submission["score"] == 37.5
    assert block.runtime.published_events[-1]["event_data"]["value"] == 37.5

    # Submission 2: Fixed code passes 4 of 4
    code_full = "a, b = map(int, input().split())\nprint(a + b)"
    res2 = handle_submit_request(block, {"language": "python", "code": code_full}, client=client)
    assert res2["passed_count"] == 4
    assert block.attempts == 2
    assert block.last_submission["score"] == 50.0
    assert block.last_submission["attempt_number"] == 2
    assert block.runtime.published_events[-1]["event_data"]["value"] == 50.0
    assert len(block.submission_history) == 2
    print("      ✓ Partial score correctly scaled; repeated submission updated gradebook to 50.0")


def test_cpp_and_java_end_to_end_submissions():
    print("[4/5] Testing C++ and Java end-to-end submissions with grade publishing...")
    block = MockCodingExamBlock(max_points=100.0)
    client = Judge0Client()

    # C++ Submission
    cpp_code = """
#include <iostream>
using namespace std;
int main() {
    int a, b;
    if (cin >> a >> b) {
        cout << a + b << endl;
    }
    return 0;
}
"""
    res_cpp = handle_submit_request(block, {"language": "cpp", "code": cpp_code}, client=client)
    assert res_cpp["passed_count"] == 4
    assert res_cpp["score"] == 100.0
    assert block.runtime.published_events[-1]["event_data"]["value"] == 100.0

    # Java Submission
    java_code = """
import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        if (sc.hasNextInt()) {
            int a = sc.nextInt();
            int b = sc.nextInt();
            System.out.println(a + b);
        }
    }
}
"""
    res_java = handle_submit_request(block, {"language": "java", "code": java_code}, client=client)
    assert res_java["passed_count"] == 4
    assert res_java["score"] == 100.0
    assert block.runtime.published_events[-1]["event_data"]["value"] == 100.0
    print("      ✓ C++ and Java submissions executed, graded, and published 100.0 successfully")


def test_compilation_error_submission():
    print("[5/5] Testing compilation error submission produces zero score and grade 0...")
    block = MockCodingExamBlock(max_points=100.0)
    client = Judge0Client()
    broken_code = "int main() { broken <<< syntax }"

    res = handle_submit_request(block, {"language": "cpp", "code": broken_code}, client=client)
    assert res["status"] == "compilation_error"
    assert res["score"] == 0.0
    assert res["percentage"] == 0.0
    assert res["passed_count"] == 0
    # Grade 0 published
    assert block.runtime.published_events[-1]["event_data"]["value"] == 0.0
    assert block.last_submission["score"] == 0.0
    assert block.last_submission["status"] == "compilation_error"
    print("      ✓ Compilation error safely published 0.0 grade and recorded failure in attempts")


if __name__ == "__main__":
    print("===================================================================")
    print("         DAY 5 RUN, SUBMIT, GRADE & ATTEMPT VERIFICATION           ")
    print("===================================================================")
    test_run_handler_does_not_publish_grade()
    test_submit_handler_publishes_grade_and_stores_attempt()
    test_partial_scoring_and_repeated_submissions()
    test_cpp_and_java_end_to_end_submissions()
    test_compilation_error_submission()
    print("===================================================================")
    print("             ALL DAY 5 TESTS PASSED SUCCESSFULLY!                  ")
    print("===================================================================")

