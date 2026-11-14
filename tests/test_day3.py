"""
Test Suite for Day 3 Backend Development: Execution Client
Verifies Python, C++, Java execution, polling, error mapping, timeouts, and sandbox fallback.
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

from coding_exam.runner.client import Judge0Client
from coding_exam.runner.docker_client import DockerSandboxClient


def test_python_synchronous_stdin():
    print("[1/9] Testing Python execution with stdin...")
    client = Judge0Client()
    res = client.execute("x = input()\nprint('Echo: ' + x)", "python", stdin="Hello Day 3")
    assert res.status == "ACCEPTED", f"Expected ACCEPTED, got {res.status}"
    assert res.is_success is True
    assert "Echo: Hello Day 3" in res.stdout
    assert bool(res.token) is True
    print(f"      ✓ Python passed (Time: {res.execution_time}s, Token: {res.token[:8]}...)")


def test_cpp_synchronous_stdin():
    print("[2/9] Testing C++ execution with stdin...")
    client = Judge0Client()
    code = "#include <iostream>\nint main() { int a, b; std::cin >> a >> b; std::cout << (a + b); return 0; }"
    res = client.execute(code, "cpp", stdin="40 2")
    assert res.status == "ACCEPTED", f"Expected ACCEPTED, got {res.status}"
    assert res.is_success is True
    assert res.stdout.strip() == "42"
    print(f"      ✓ C++ passed (Time: {res.execution_time}s)")


def test_java_synchronous_stdin():
    print("[3/9] Testing Java execution with stdin...")
    client = Judge0Client()
    code = """
import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner s = new Scanner(System.in);
        int v = s.nextInt();
        System.out.println("Java: " + (v * 10));
    }
}
"""
    res = client.execute(code, "java", stdin="7")
    assert res.status == "ACCEPTED", f"Expected ACCEPTED, got {res.status}"
    assert res.is_success is True
    assert "Java: 70" in res.stdout
    print(f"      ✓ Java passed (Time: {res.execution_time}s)")


def test_polling_and_retrieval():
    print("[4/9] Testing asynchronous submission & token polling (wait=False)...")
    client = Judge0Client()
    res = client.execute(
        "print('Polled Output!')",
        "python",
        wait=False,
        poll_if_queued=True,
        max_polls=10,
        poll_interval=0.5,
    )
    assert res.status == "ACCEPTED", f"Expected ACCEPTED after polling, got {res.status}"
    assert "Polled Output!" in res.stdout
    assert bool(res.token) is True
    print(f"      ✓ Asynchronous polling passed (Token: {res.token[:8]}...)")


def test_compilation_error_mapping():
    print("[5/9] Testing C++ compilation error mapping...")
    client = Judge0Client()
    res = client.execute("int main() { syntax error <<< }", "cpp")
    assert res.status == "COMPILATION_ERROR", f"Expected COMPILATION_ERROR, got {res.status}"
    assert res.is_success is False
    assert res.status_id == 6
    assert "error" in res.compile_output.lower()
    print(f"      ✓ Compilation error mapping passed (Status ID: {res.status_id})")


def test_runtime_error_mapping():
    print("[6/9] Testing Python runtime error mapping (ZeroDivisionError)...")
    client = Judge0Client()
    res = client.execute("a = 1 / 0", "python")
    assert res.status == "RUNTIME_ERROR", f"Expected RUNTIME_ERROR, got {res.status}"
    assert res.is_success is False
    assert "ZeroDivisionError" in res.stderr
    print(f"      ✓ Runtime error mapping passed (Status ID: {res.status_id})")


def test_timeout_mapping():
    print("[7/9] Testing timeout mapping (Time Limit Exceeded)...")
    client = Judge0Client()
    res = client.execute("while True: pass", "python", cpu_time_limit=2.0)
    assert res.status == "TIME_LIMIT_EXCEEDED", f"Expected TIME_LIMIT_EXCEEDED, got {res.status}"
    assert res.is_success is False
    assert res.status_id == 5
    print(f"      ✓ Timeout mapping passed (Elapsed: {res.execution_time}s)")


def test_wrong_answer_separation():
    print("[8/9] Testing engine health vs. wrong answer separation...")
    client = Judge0Client()
    res = client.execute("print(100)", "python")
    assert res.status == "ACCEPTED", f"Expected ACCEPTED, got {res.status}"
    assert res.is_success is True
    print("      ✓ Engine reports ACCEPTED (wrong-answer check deferred to test runner)")


def test_docker_sandbox_fallback():
    print("[9/9] Testing Docker sandbox client fallback...")
    docker_client = DockerSandboxClient()
    res = docker_client.execute("print('Docker Sandbox Works!')", "python")
    assert res.status == "ACCEPTED", f"Expected ACCEPTED, got {res.status}"
    assert "Docker Sandbox Works!" in res.stdout

    res_err = docker_client.execute("int main() { bad <<< }", "cpp")
    assert res_err.status == "COMPILATION_ERROR"
    print("      ✓ Docker sandbox client fallback passed")


if __name__ == "__main__":
    print("===================================================================")
    print("             DAY 3 EXECUTION CLIENT VERIFICATION SUITE             ")
    print("===================================================================")
    test_python_synchronous_stdin()
    test_cpp_synchronous_stdin()
    test_java_synchronous_stdin()
    test_polling_and_retrieval()
    test_compilation_error_mapping()
    test_runtime_error_mapping()
    test_timeout_mapping()
    test_wrong_answer_separation()
    test_docker_sandbox_fallback()
    print("===================================================================")
    print("             ALL DAY 3 TESTS PASSED SUCCESSFULLY!                  ")
    print("===================================================================")

