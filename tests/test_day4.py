"""
Test Suite for Day 4 Backend Development: Test Case Runner
Verifies multi-case execution, output normalization, visible vs hidden masking,
action filtering ('run' vs 'submit'), scoring integration, and client interoperability.
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
    DockerSandboxClient,
    Judge0Client,
    TestCase,
    normalize_output,
    run_submission,
    run_test_cases,
)


def test_output_normalization():
    print("[1/6] Testing whitespace & newline normalization...")
    assert normalize_output("42   \r\n") == "42"
    assert normalize_output("\n\n100\n200\n\n") == "100\n200"
    assert normalize_output("line 1   \nline 2   \r\n") == "line 1\nline 2"
    print("      ✓ normalize_output handles CRLF, trailing spaces, and blank lines")


def test_python_multiple_test_cases():
    print("[2/6] Testing Python multiple test cases (Visible & Hidden)...")
    client = Judge0Client()
    py_code = """
a = int(input())
b = int(input())
print(a + b)
"""
    test_cases = [
        TestCase(id=1, input="10\n20\n", expected_output="30", is_hidden=False),
        TestCase(id=2, input="100\n-50\n", expected_output="50", is_hidden=False),
        TestCase(id=3, input="999\n1\n", expected_output="1000", is_hidden=True),
        TestCase(id=4, input="5\n5\n", expected_output="999", is_hidden=True),  # Deliberate fail
    ]

    res = run_test_cases(client, py_code, "python", test_cases)
    assert res["total_count"] == 4
    assert res["passed_count"] == 3

    # Verify hidden test case masking
    hidden_pass = [r for r in res["results"] if r["test_case_id"] == 3][0]
    assert hidden_pass["passed"] is True
    assert hidden_pass["input"] == "[Hidden]"
    assert hidden_pass["expected_output"] == "[Hidden]"
    assert hidden_pass["actual_output"] == "[Hidden]"

    hidden_fail = [r for r in res["results"] if r["test_case_id"] == 4][0]
    assert hidden_fail["passed"] is False
    assert hidden_fail["input"] == "[Hidden]"
    assert hidden_fail["expected_output"] == "[Hidden]"
    assert hidden_fail["actual_output"] == "[Hidden]"
    print("      ✓ Python test cases evaluated with strict hidden case masking")


def test_cpp_multiple_test_cases():
    print("[3/6] Testing C++ multiple test cases...")
    client = Judge0Client()
    cpp_code = """
#include <iostream>
int main() {
    int n;
    if (std::cin >> n) {
        std::cout << (n * n) << std::endl;
    }
    return 0;
}
"""
    test_cases = [
        TestCase(id="tc-1", input="4\n", expected_output="16", is_hidden=False),
        TestCase(id="tc-2", input="12\n", expected_output="144", is_hidden=True),
    ]
    res = run_test_cases(client, cpp_code, "cpp", test_cases)
    assert res["total_count"] == 2
    assert res["passed_count"] == 2
    print("      ✓ C++ test cases evaluated successfully")


def test_java_multiple_test_cases():
    print("[4/6] Testing Java multiple test cases...")
    client = Judge0Client()
    java_code = """
import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        String s = sc.nextLine();
        System.out.println("Echo: " + s);
    }
}
"""
    test_cases = [
        TestCase(id=1, input="Alpha", expected_output="Echo: Alpha", is_hidden=False),
        TestCase(id=2, input="Beta", expected_output="Echo: Beta", is_hidden=True),
    ]
    res = run_test_cases(client, java_code, "java", test_cases)
    assert res["total_count"] == 2
    assert res["passed_count"] == 2
    print("      ✓ Java test cases evaluated successfully")


def test_run_submission_action_filtering():
    print("[5/6] Testing run_submission() action filtering ('run' vs 'submit')...")
    client = Judge0Client()
    raw_cases = [
        {"id": 1, "input": "3 4", "expected_output": "7", "is_hidden": False},
        {"id": 2, "input": "10 20", "expected_output": "30", "is_hidden": False},
        {"id": 3, "input": "50 50", "expected_output": "100", "is_hidden": True},
        {"id": 4, "input": "0 0", "expected_output": "0", "is_hidden": True},
    ]
    add_code = "a, b = map(int, input().split())\nprint(a + b)"

    # Action: 'run' must only evaluate visible test cases (cases 1 and 2)
    resp_run = run_submission(client, add_code, "python", raw_cases, action="run")
    assert resp_run["action"] == "run"
    assert resp_run["total_count"] == 2, f"Expected 2 visible test cases, got {resp_run['total_count']}"
    assert resp_run["passed_count"] == 2

    # Action: 'submit' must evaluate all test cases (cases 1, 2, 3, 4)
    resp_submit = run_submission(client, add_code, "python", raw_cases, action="submit")
    assert resp_submit["action"] == "submit"
    assert resp_submit["total_count"] == 4, f"Expected 4 test cases, got {resp_submit['total_count']}"
    assert resp_submit["passed_count"] == 4
    assert resp_submit["score"] == 1.0
    assert resp_submit["percentage"] == 100.0
    print("      ✓ action='run' filters to visible only; action='submit' runs all and scores")


def test_docker_sandbox_interoperability():
    print("[6/6] Testing Docker sandbox client interoperability with run_submission()...")
    docker_client = DockerSandboxClient()
    raw_cases = [
        {"id": 1, "input": "2 3", "expected_output": "5", "is_hidden": False},
        {"id": 2, "input": "7 8", "expected_output": "15", "is_hidden": True},
    ]
    add_code = "a, b = map(int, input().split())\nprint(a + b)"
    resp_docker = run_submission(docker_client, add_code, "python", raw_cases, action="submit")
    assert resp_docker["passed_count"] == 2
    assert resp_docker["percentage"] == 100.0
    print("      ✓ Docker sandbox client fully interoperable with test runner and scoring")


if __name__ == "__main__":
    print("===================================================================")
    print("             DAY 4 TEST CASE RUNNER VERIFICATION SUITE             ")
    print("===================================================================")
    test_output_normalization()
    test_python_multiple_test_cases()
    test_cpp_multiple_test_cases()
    test_java_multiple_test_cases()
    test_run_submission_action_filtering()
    test_docker_sandbox_interoperability()
    print("===================================================================")
    print("             ALL DAY 4 TESTS PASSED SUCCESSFULLY!                  ")
    print("===================================================================")

