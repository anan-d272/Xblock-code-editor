"""
Comprehensive Day 8 QA & Verification Test Suite.
Tests:
  1. Unit tests for scoring.py (bounds, zero tests, percentages, scaling)
  2. Unit tests for tester.py (whitespace normalization, test case filtering, masking)
  3. Unit tests for client.py and docker_client.py
  4. Backend handler tests (Run vs Submit, grade publishing, attempt storage)
  5. Edge case tests (Infinite loop, Compilation error, Large output, Memory limit, Runtime error, Wrong answer)
  6. Standard language tests (Python, Java, C++ sum of two integers)
  7. Five additional algorithmic problems in Java and C++:
     - Largest of 3 numbers
     - Prime number check
     - Reverse a string
     - Factorial calculation
     - Palindrome string check
"""
import os
import sys
from unittest.mock import MagicMock

# Mock web_fragments and xblock for host-side unit testing
for mod in ["web_fragments", "web_fragments.fragment", "xblock", "xblock.core", "xblock.fields"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from coding_exam.runner.scoring import calculate_score
from coding_exam.runner.tester import TestCase, TestCaseResult, normalize_output, run_submission, run_test_cases
from coding_exam.runner.client import ExecutionResult, Judge0Client
from coding_exam.runner.docker_client import DockerSandboxClient
from coding_exam.runner.handlers import handle_run_request, handle_submit_request


# =====================================================================
# SECTION 1: UNIT TESTS — SCORING (scoring.py)
# =====================================================================

def test_scoring_unit():
    print("[Unit: Scoring] Testing scoring logic across all boundary conditions...")
    # 1. All passed
    s1 = calculate_score(10, 10, max_points=100.0)
    assert s1["score"] == 100.0
    assert s1["percentage"] == 100.0
    assert s1["passed_count"] == 10
    assert "All 10 test cases passed" in s1["feedback"]

    # 2. None passed
    s2 = calculate_score(0, 10, max_points=100.0)
    assert s2["score"] == 0.0
    assert s2["percentage"] == 0.0
    assert s2["passed_count"] == 0
    assert "0 of 10 test cases passed" in s2["feedback"]

    # 3. Partial pass (8 of 10 with max_points=100)
    s3 = calculate_score(8, 10, max_points=100.0)
    assert s3["score"] == 80.0
    assert s3["percentage"] == 80.0
    assert s3["passed_count"] == 8

    # 4. Zero test cases (edge case)
    s4 = calculate_score(0, 0, max_points=100.0)
    assert s4["score"] == 0.0
    assert s4["percentage"] == 0.0
    assert s4["total_count"] == 0
    assert "No test cases configured" in s4["feedback"]

    # 5. Non-standard max points (e.g. 33.33)
    s5 = calculate_score(1, 3, max_points=33.33)
    assert round(s5["score"], 2) == 11.11
    assert s5["percentage"] == 33.33

    # 6. Overflow / negative bound defense
    s6 = calculate_score(15, 10, max_points=50.0)  # passed > total
    assert s6["score"] == 50.0
    assert s6["passed_count"] == 10

    s7 = calculate_score(-5, 10, max_points=50.0)  # passed < 0
    assert s7["score"] == 0.0
    assert s7["passed_count"] == 0

    print("      ✓ scoring.py verified across all edge cases (100% passed)")


# =====================================================================
# SECTION 2: UNIT TESTS — TEST CASE RUNNER (tester.py)
# =====================================================================

def test_tester_unit():
    print("[Unit: Tester] Testing test case runner & normalization...")
    # 1. Output normalization
    assert normalize_output("hello world  \r\n") == "hello world"
    assert normalize_output("\n\n  30 \n\n") == "30"
    assert normalize_output("line 1   \r\nline 2   \r\n") == "line 1\nline 2"
    assert normalize_output("") == ""
    assert normalize_output(None) == ""

    # 2. Mock execution client for deterministic runner testing
    class MockClient:
        def execute(self, source_code, language, stdin="", **kwargs):
            val = stdin.strip()
            if val == "crash":
                return ExecutionResult("RUNTIME_ERROR", False, "", "Division by zero", "", 0.01, 0, 11, "NZEC")
            if val == "timeout":
                return ExecutionResult("TIME_LIMIT_EXCEEDED", False, "", "Timeout", "", 5.0, 0, 5, "TLE")
            if val == "compile_fail":
                return ExecutionResult("COMPILATION_ERROR", False, "", "Syntax error", "Syntax error", 0.0, 0, 6, "CE")
            return ExecutionResult("ACCEPTED", True, f"out:{val}", "", "", 0.01, 1024, 3, "Accepted")

    client = MockClient()
    test_cases = [
        TestCase(id=1, input="10", expected_output="out:10", is_hidden=False),
        TestCase(id=2, input="20", expected_output="out:wrong", is_hidden=False),
        TestCase(id=3, input="secret", expected_output="out:secret", is_hidden=True),
        TestCase(id=4, input="crash", expected_output="out:crash", is_hidden=False),
    ]

    res = run_test_cases(client, "dummy_code", "python", test_cases)
    assert res["total_count"] == 4
    assert res["passed_count"] == 2  # tc 1 and tc 3 pass
    
    # Check hidden case masking
    tc3_res = res["results"][2]
    assert tc3_res["is_hidden"] is True
    assert tc3_res["input"] == "[Hidden]"
    assert tc3_res["expected_output"] == "[Hidden]"
    assert tc3_res["actual_output"] == "[Hidden]"
    assert tc3_res["passed"] is True

    # Check wrong answer detection
    tc2_res = res["results"][1]
    assert tc2_res["passed"] is False
    assert tc2_res["status"] == "WRONG_ANSWER"

    # Check runtime error handling
    tc4_res = res["results"][3]
    assert tc4_res["passed"] is False
    assert tc4_res["status"] == "RUNTIME_ERROR"

    print("      ✓ tester.py verified (normalization, hidden masking, wrong answer, runtime error)")


# =====================================================================
# SECTION 3: UNIT TESTS — EXECUTION CLIENTS (client.py, docker_client.py)
# =====================================================================

def test_clients_unit():
    print("[Unit: Clients] Testing Judge0Client & DockerSandboxClient initialization...")
    # 1. Judge0Client language mapping and headers
    j_client = Judge0Client()
    assert j_client.get_language_id("python") == 71
    assert j_client.get_language_id("cpp") == 54
    assert j_client.get_language_id("java") == 62
    assert j_client.user_agent == "OpenEdX-CodingExam/1.0"

    try:
        j_client.get_language_id("ruby")
        assert False, "Should raise ValueError for unsupported language"
    except ValueError:
        pass

    # 2. DockerSandboxClient options
    d_client = DockerSandboxClient(cpu_limit="0.5", memory_limit="128m", default_timeout=5, max_output_bytes=1048576)
    assert d_client.cpu_limit == "0.5"
    assert d_client.memory_limit == "128m"
    assert d_client.default_timeout == 5
    assert d_client.max_output_bytes == 1048576

    print("      ✓ client.py and docker_client.py unit configurations verified")


# =====================================================================
# SECTION 4: BACKEND HANDLERS TESTS (handlers.py)
# =====================================================================

class MockBlockState:
    def __init__(self, max_points=100.0, attempts=0):
        self.max_points = max_points
        self.attempts = attempts
        self.last_submission = {}
        self.submission_history = []
        self.runtime = MagicMock()
        self.runtime.published = []
        self.runtime.publish = lambda b, evt, data: self.runtime.published.append((evt, data))
        self.scope_ids = MagicMock(user_id="learner_teerth")
        self.test_cases = [
            {"id": 1, "input": "10 20\n", "expected_output": "30", "is_hidden": False},
            {"id": 2, "input": "5 -2\n", "expected_output": "3", "is_hidden": True},
        ]


def test_backend_handlers():
    print("[Unit: Handlers] Testing Run vs Submit handlers and grade publishing...")
    block = MockBlockState(max_points=50.0)
    client = DockerSandboxClient()

    code = "a, b = map(int, input().split())\nprint(a + b)"

    # 1. Run Handler: Visible tests only, NO grade publication
    run_res = handle_run_request(block, {"language": "python", "code": code}, client=client)
    assert run_res["action"] == "run"
    assert run_res["total_count"] == 1  # only 1 visible test case
    assert run_res["passed_count"] == 1
    assert len(block.runtime.published) == 0, "Run handler must NEVER publish grades!"
    assert block.attempts == 0, "Run handler must NEVER increment attempts!"

    # 2. Submit Handler: All tests (visible + hidden), publishes grade, increments attempts
    sub_res = handle_submit_request(block, {"language": "python", "code": code}, client=client)
    assert sub_res["action"] == "submit"
    assert sub_res["total_count"] == 2  # visible + hidden
    assert sub_res["passed_count"] == 2
    assert sub_res["score"] == 50.0
    assert len(block.runtime.published) == 1, "Submit handler MUST publish grade to LMS gradebook!"
    assert block.runtime.published[0][1]["value"] == 50.0
    assert block.attempts == 1
    assert len(block.submission_history) == 1
    assert block.last_submission["attempt_number"] == 1

    print("      ✓ Handlers verified (Run: 0 grades/0 attempts; Submit: grade published + attempt recorded)")


# =====================================================================
# SECTION 5: EDGE CASE TESTING (Isolated Docker Sandbox)
# =====================================================================

def test_edge_cases():
    print("[Edge Cases] Executing edge cases in isolated Docker sandbox...")
    sandbox = DockerSandboxClient(default_timeout=3, max_output_bytes=2048)

    # TEST 1: Infinite loop
    print("      -> Testing infinite loop (timeout enforcement)...")
    loop_code = "while True: pass"
    res_loop = sandbox.execute(loop_code, "python", cpu_time_limit=2)
    assert res_loop.status == "TIME_LIMIT_EXCEEDED"
    assert res_loop.is_success is False
    print("         ✓ Infinite loop terminated within timeout quota (Status: TIME_LIMIT_EXCEEDED)")

    # TEST 2: Compilation error (Invalid C++)
    print("      -> Testing compilation error (C++ syntax error)...")
    broken_cpp = "#include <iostream>\nint main() { broken <<< syntax; return 0; }"
    res_comp = sandbox.execute(broken_cpp, "cpp")
    assert res_comp.status == "COMPILATION_ERROR"
    assert res_comp.is_success is False
    assert len(res_comp.compile_output) > 0
    print("         ✓ Compilation error detected with diagnostic output captured")

    # TEST 3: Large output flood
    print("      -> Testing large output flood (clamping to quota)...")
    flood_code = "print('Z' * 50000)"
    res_flood = sandbox.execute(flood_code, "python")
    assert len(res_flood.stdout) <= 2048, f"Output not capped: got {len(res_flood.stdout)} bytes"
    print(f"         ✓ Large output strictly capped to {len(res_flood.stdout)} bytes without host exhaustion")

    # TEST 4: Controlled Memory Limit
    print("      -> Testing memory limit exhaustion...")
    # Allocating ~200MB inside a 32MB container
    oom_code = """
try:
    arr = [' ' * (1024 * 1024) for _ in range(250)]
    print('Allocated', len(arr))
except MemoryError:
    print('Caught MemoryError')
"""
    res_oom = sandbox.execute(oom_code, "python", memory_limit=32000)
    # The process is terminated by cgroup OOM or raises MemoryError / runtime error
    assert res_oom.status in ("RUNTIME_ERROR", "TIME_LIMIT_EXCEEDED") or "MemoryError" in res_oom.stdout
    print("         ✓ Memory restriction safely enforced by Docker cgroups")

    # TEST 5: Runtime error (ZeroDivisionError)
    print("      -> Testing runtime error detection...")
    runtime_code = "a = 10 / 0"
    res_err = sandbox.execute(runtime_code, "python")
    assert res_err.status == "RUNTIME_ERROR"
    assert "ZeroDivisionError" in res_err.stderr
    print("         ✓ Runtime error captured with traceback in stderr")

    # TEST 6: Incorrect output comparison
    print("      -> Testing incorrect output classification...")
    wa_code = "print(999)"
    wa_cases = [TestCase(id=1, input="10 20\n", expected_output="30", is_hidden=False)]
    wa_res = run_test_cases(sandbox, wa_code, "python", wa_cases)
    assert wa_res["passed_count"] == 0
    assert wa_res["results"][0]["status"] == "WRONG_ANSWER"
    print("         ✓ Incorrect output properly classified as WRONG_ANSWER")


# =====================================================================
# SECTION 6: PROGRAMMING LANGUAGE TESTING (Python, Java, C++)
# =====================================================================

def test_programming_languages():
    print("[Languages] Testing Python, Java, and C++ sum of two integers...")
    sandbox = DockerSandboxClient(default_timeout=5)
    test_cases = [
        TestCase(id=1, input="10 20\n", expected_output="30", is_hidden=False),
        TestCase(id=2, input="5 -2\n", expected_output="3", is_hidden=False),
        TestCase(id=3, input="100 250\n", expected_output="350", is_hidden=True),
    ]

    # 1. Python
    py_code = "a, b = map(int, input().split())\nprint(a + b)"
    py_res = run_test_cases(sandbox, py_code, "python", test_cases)
    assert py_res["passed_count"] == 3
    print("      ✓ Python: 3 of 3 test cases passed")

    # 2. C++
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
    cpp_res = run_test_cases(sandbox, cpp_code, "cpp", test_cases)
    assert cpp_res["passed_count"] == 3
    print("      ✓ C++: 3 of 3 test cases passed")

    # 3. Java
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
    java_res = run_test_cases(sandbox, java_code, "java", test_cases)
    assert java_res["passed_count"] == 3
    print("      ✓ Java: 3 of 3 test cases passed")


# =====================================================================
# SECTION 7: FIVE ADDITIONAL SAMPLE PROBLEMS (Java and C++)
# =====================================================================

def test_additional_sample_problems():
    print("[Additional Problems] Testing 5 algorithmic problems in Java and C++...")
    sandbox = DockerSandboxClient(default_timeout=10)

    # -----------------------------------------------------------------
    # Problem 1: Find Largest of Three Numbers
    # -----------------------------------------------------------------
    print("      [1/5] Largest of Three Numbers...")
    p1_cases = [
        TestCase(id=1, input="10 50 30\n", expected_output="50", is_hidden=False),
        TestCase(id=2, input="-5 -1 -10\n", expected_output="-1", is_hidden=False),
        TestCase(id=3, input="42 42 42\n", expected_output="42", is_hidden=True),
    ]
    cpp_p1 = """
#include <iostream>
#include <algorithm>
using namespace std;
int main() {
    long long a, b, c;
    if (cin >> a >> b >> c) {
        cout << max(a, max(b, c)) << endl;
    }
    return 0;
}
"""
    assert run_test_cases(sandbox, cpp_p1, "cpp", p1_cases)["passed_count"] == 3

    java_p1 = """
import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        long a = sc.nextLong();
        long b = sc.nextLong();
        long c = sc.nextLong();
        System.out.println(Math.max(a, Math.max(b, c)));
    }
}
"""
    assert run_test_cases(sandbox, java_p1, "java", p1_cases)["passed_count"] == 3
    print("            ✓ C++ and Java passed Largest of Three Numbers")

    # -----------------------------------------------------------------
    # Problem 2: Check Whether Number is Prime
    # -----------------------------------------------------------------
    print("      [2/5] Prime Number Verification...")
    p2_cases = [
        TestCase(id=1, input="7\n", expected_output="PRIME", is_hidden=False),
        TestCase(id=2, input="1\n", expected_output="NOT_PRIME", is_hidden=False),
        TestCase(id=3, input="4\n", expected_output="NOT_PRIME", is_hidden=False),
        TestCase(id=4, input="97\n", expected_output="PRIME", is_hidden=True),
    ]
    cpp_p2 = """
#include <iostream>
using namespace std;
bool isPrime(long long n) {
    if (n <= 1) return false;
    for (long long i = 2; i * i <= n; i++) {
        if (n % i == 0) return false;
    }
    return true;
}
int main() {
    long long n;
    if (cin >> n) {
        cout << (isPrime(n) ? "PRIME" : "NOT_PRIME") << endl;
    }
    return 0;
}
"""
    assert run_test_cases(sandbox, cpp_p2, "cpp", p2_cases)["passed_count"] == 4

    java_p2 = """
import java.util.Scanner;
public class Main {
    static boolean isPrime(long n) {
        if (n <= 1) return false;
        for (long i = 2; i * i <= n; i++) {
            if (n % i == 0) return false;
        }
        return true;
    }
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        long n = sc.nextLong();
        System.out.println(isPrime(n) ? "PRIME" : "NOT_PRIME");
    }
}
"""
    assert run_test_cases(sandbox, java_p2, "java", p2_cases)["passed_count"] == 4
    print("            ✓ C++ and Java passed Prime Number Verification")

    # -----------------------------------------------------------------
    # Problem 3: Reverse a String
    # -----------------------------------------------------------------
    print("      [3/5] Reverse a String...")
    p3_cases = [
        TestCase(id=1, input="OpenEdX\n", expected_output="XdEnepO", is_hidden=False),
        TestCase(id=2, input="hello world\n", expected_output="dlrow olleh", is_hidden=False),
        TestCase(id=3, input="racecar\n", expected_output="racecar", is_hidden=True),
    ]
    cpp_p3 = """
#include <iostream>
#include <string>
#include <algorithm>
using namespace std;
int main() {
    string s;
    if (getline(cin, s)) {
        reverse(s.begin(), s.end());
        cout << s << endl;
    }
    return 0;
}
"""
    assert run_test_cases(sandbox, cpp_p3, "cpp", p3_cases)["passed_count"] == 3

    java_p3 = """
import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        if (sc.hasNextLine()) {
            String s = sc.nextLine();
            System.out.println(new StringBuilder(s).reverse().toString());
        }
    }
}
"""
    assert run_test_cases(sandbox, java_p3, "java", p3_cases)["passed_count"] == 3
    print("            ✓ C++ and Java passed Reverse a String")

    # -----------------------------------------------------------------
    # Problem 4: Factorial Calculation
    # -----------------------------------------------------------------
    print("      [4/5] Factorial Calculation...")
    p4_cases = [
        TestCase(id=1, input="0\n", expected_output="1", is_hidden=False),
        TestCase(id=2, input="5\n", expected_output="120", is_hidden=False),
        TestCase(id=3, input="10\n", expected_output="3628800", is_hidden=True),
    ]
    cpp_p4 = """
#include <iostream>
using namespace std;
int main() {
    int n;
    if (cin >> n) {
        long long f = 1;
        for (int i = 1; i <= n; i++) f *= i;
        cout << f << endl;
    }
    return 0;
}
"""
    assert run_test_cases(sandbox, cpp_p4, "cpp", p4_cases)["passed_count"] == 3

    java_p4 = """
import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int n = sc.nextInt();
        long f = 1;
        for (int i = 1; i <= n; i++) f *= i;
        System.out.println(f);
    }
}
"""
    assert run_test_cases(sandbox, java_p4, "java", p4_cases)["passed_count"] == 3
    print("            ✓ C++ and Java passed Factorial Calculation")

    # -----------------------------------------------------------------
    # Problem 5: Palindrome String Check
    # -----------------------------------------------------------------
    print("      [5/5] Palindrome String Verification...")
    p5_cases = [
        TestCase(id=1, input="madam\n", expected_output="PALINDROME", is_hidden=False),
        TestCase(id=2, input="edx\n", expected_output="NOT_PALINDROME", is_hidden=False),
        TestCase(id=3, input="deified\n", expected_output="PALINDROME", is_hidden=True),
    ]
    cpp_p5 = """
#include <iostream>
#include <string>
#include <algorithm>
using namespace std;
int main() {
    string s;
    if (cin >> s) {
        string r = s;
        reverse(r.begin(), r.end());
        cout << (s == r ? "PALINDROME" : "NOT_PALINDROME") << endl;
    }
    return 0;
}
"""
    assert run_test_cases(sandbox, cpp_p5, "cpp", p5_cases)["passed_count"] == 3

    java_p5 = """
import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        String s = sc.next();
        String r = new StringBuilder(s).reverse().toString();
        System.out.println(s.equals(r) ? "PALINDROME" : "NOT_PALINDROME");
    }
}
"""
    assert run_test_cases(sandbox, java_p5, "java", p5_cases)["passed_count"] == 3
    print("            ✓ C++ and Java passed Palindrome String Verification")


# =====================================================================
# MAIN RUNNER
# =====================================================================

if __name__ == "__main__":
    print("===================================================================")
    print("       DAY 8 BACKEND TESTING & QUALITY ASSURANCE SUITE             ")
    print("===================================================================")
    try:
        test_scoring_unit()
        test_tester_unit()
        test_clients_unit()
        test_backend_handlers()
        test_edge_cases()
        test_programming_languages()
        test_additional_sample_problems()
        print("===================================================================")
        print("         ALL DAY 8 QA & VERIFICATION TESTS PASSED!                 ")
        print("===================================================================")
    except AssertionError as e:
        print(f"\n[FAIL] Assertion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
