"""
Test case runner and evaluation engine.
Executes test cases against submitted code, normalizes outputs, compares results,
and computes final submission scores.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable

from .client import ExecutionResult, Judge0Client
from .scoring import calculate_score


@runtime_checkable
class ExecutionClientProtocol(Protocol):
    """Protocol defining the interface expected of any execution client."""
    def execute(
        self,
        source_code: str,
        language: str,
        stdin: str = "",
        cpu_time_limit: Optional[float] = None,
        memory_limit: Optional[int] = None,
        **kwargs: Any,
    ) -> ExecutionResult:
        ...


@dataclass
class TestCase:
    """Represents a single test case with input and expected output."""
    id: Any
    input: str
    expected_output: str
    is_hidden: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any], default_id: int = 1) -> "TestCase":
        """Instantiate a TestCase from a dictionary payload."""
        return cls(
            id=data.get("id", data.get("test_case_id", default_id)),
            input=str(data.get("input", "")),
            expected_output=str(data.get("expected_output", "")),
            is_hidden=bool(data.get("is_hidden", False)),
        )


@dataclass
class TestCaseResult:
    """Outcome of evaluating a single test case."""
    test_case_id: Any
    passed: bool
    is_hidden: bool
    input: str
    expected_output: str
    actual_output: str
    status: str
    error_message: str
    execution_time: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary suitable for JSON serialization."""
        return {
            "test_case_id": self.test_case_id,
            "passed": self.passed,
            "is_hidden": self.is_hidden,
            "input": self.input,
            "expected_output": self.expected_output,
            "actual_output": self.actual_output,
            "status": self.status,
            "error_message": self.error_message,
            "execution_time": self.execution_time,
        }


def normalize_output(text: Optional[str]) -> str:
    """
    Normalize program output for robust comparison:
    1. Unify CRLF to LF line endings.
    2. Strip trailing whitespace from every individual line.
    3. Strip leading and trailing empty lines / outer whitespace.
    """
    if not text:
        return ""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def run_test_cases(
    client: Any,
    source_code: str,
    language: str,
    test_cases: List[TestCase],
    cpu_time_limit: Optional[float] = None,
    memory_limit: Optional[int] = None,
    stop_on_compilation_error: bool = True,
) -> Dict[str, Any]:
    """
    Execute student code against a list of test cases.

    :param client: Execution client (Judge0Client, DockerSandboxClient, etc.)
    :param source_code: Source code submitted by student
    :param language: Programming language ('python', 'cpp', 'java')
    :param test_cases: List of TestCase objects
    :param cpu_time_limit: Maximum CPU time in seconds per test case
    :param memory_limit: Maximum memory in kilobytes
    :param stop_on_compilation_error: If True, halts execution on compilation error
    :return: Dictionary containing test summary and detailed results per test case
    """
    results: List[TestCaseResult] = []
    passed_count = 0
    total_count = len(test_cases)
    compilation_error: Optional[str] = None

    for idx, tc in enumerate(test_cases):
        # If compilation failed on an earlier test case, skip sending remaining requests
        if compilation_error and stop_on_compilation_error:
            results.append(
                TestCaseResult(
                    test_case_id=tc.id,
                    passed=False,
                    is_hidden=tc.is_hidden,
                    input="[Hidden]" if tc.is_hidden else tc.input,
                    expected_output="[Hidden]" if tc.is_hidden else tc.expected_output,
                    actual_output="[Hidden]" if tc.is_hidden else "",
                    status="SKIPPED",
                    error_message="Skipped due to previous compilation error.",
                    execution_time=0.0,
                )
            )
            continue

        exec_res: ExecutionResult = client.execute(
            source_code=source_code,
            language=language,
            stdin=tc.input,
            cpu_time_limit=cpu_time_limit,
            memory_limit=memory_limit,
        )

        # Check for Compilation Error
        if exec_res.status == "COMPILATION_ERROR":
            compilation_error = exec_res.compile_output or exec_res.stderr or "Compilation failed."
            results.append(
                TestCaseResult(
                    test_case_id=tc.id,
                    passed=False,
                    is_hidden=tc.is_hidden,
                    input="[Hidden]" if tc.is_hidden else tc.input,
                    expected_output="[Hidden]" if tc.is_hidden else tc.expected_output,
                    actual_output="[Hidden]" if tc.is_hidden else "",
                    status="COMPILATION_ERROR",
                    error_message=compilation_error,
                    execution_time=exec_res.execution_time,
                )
            )
            continue

        # Check for Runtime Error
        if exec_res.status == "RUNTIME_ERROR":
            results.append(
                TestCaseResult(
                    test_case_id=tc.id,
                    passed=False,
                    is_hidden=tc.is_hidden,
                    input="[Hidden]" if tc.is_hidden else tc.input,
                    expected_output="[Hidden]" if tc.is_hidden else tc.expected_output,
                    actual_output="[Hidden]" if tc.is_hidden else exec_res.stdout,
                    status="RUNTIME_ERROR",
                    error_message=exec_res.stderr or "Runtime error occurred.",
                    execution_time=exec_res.execution_time,
                )
            )
            continue

        # Check for Time Limit Exceeded
        if exec_res.status == "TIME_LIMIT_EXCEEDED":
            results.append(
                TestCaseResult(
                    test_case_id=tc.id,
                    passed=False,
                    is_hidden=tc.is_hidden,
                    input="[Hidden]" if tc.is_hidden else tc.input,
                    expected_output="[Hidden]" if tc.is_hidden else tc.expected_output,
                    actual_output="[Hidden]" if tc.is_hidden else exec_res.stdout,
                    status="TIME_LIMIT_EXCEEDED",
                    error_message=f"Time limit exceeded ({exec_res.execution_time}s).",
                    execution_time=exec_res.execution_time,
                )
            )
            continue

        # Check for infrastructure/HTTP errors
        if not exec_res.is_success:
            results.append(
                TestCaseResult(
                    test_case_id=tc.id,
                    passed=False,
                    is_hidden=tc.is_hidden,
                    input="[Hidden]" if tc.is_hidden else tc.input,
                    expected_output="[Hidden]" if tc.is_hidden else tc.expected_output,
                    actual_output="[Hidden]" if tc.is_hidden else exec_res.stdout,
                    status=exec_res.status,
                    error_message=exec_res.stderr or exec_res.message or "Execution error.",
                    execution_time=exec_res.execution_time,
                )
            )
            continue

        # Output comparison with whitespace and line-ending normalization
        normalized_actual = normalize_output(exec_res.stdout)
        normalized_expected = normalize_output(tc.expected_output)

        passed = (normalized_actual == normalized_expected)
        if passed:
            passed_count += 1

        # Sanitize details for hidden test cases
        display_input = "[Hidden]" if tc.is_hidden else tc.input
        display_expected = "[Hidden]" if tc.is_hidden else tc.expected_output
        display_actual = "[Hidden]" if tc.is_hidden else exec_res.stdout

        results.append(
            TestCaseResult(
                test_case_id=tc.id,
                passed=passed,
                is_hidden=tc.is_hidden,
                input=display_input,
                expected_output=display_expected,
                actual_output=display_actual,
                status="PASSED" if passed else "WRONG_ANSWER",
                error_message="" if passed else "Output did not match expected output.",
                execution_time=exec_res.execution_time,
            )
        )

    return {
        "total_count": total_count,
        "passed_count": passed_count,
        "compilation_error": compilation_error,
        "results": [r.to_dict() for r in results],
    }


def run_submission(
    client: Any,
    source_code: str,
    language: str,
    test_cases_data: List[Union[Dict[str, Any], TestCase]],
    action: str = "run",
    max_points: float = 1.0,
    cpu_time_limit: Optional[float] = None,
    memory_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    High-level handler function designed for Open edX XBlock handlers.
    Takes raw test case data, filters by action ('run' vs 'submit'), evaluates,
    and returns a structured API-compliant response.

    :param client: Execution client (Judge0Client or DockerSandboxClient)
    :param source_code: Student submitted code
    :param language: Target programming language
    :param test_cases_data: List of test cases (either TestCase objects or dicts)
    :param action: 'run' (visible test cases only) or 'submit' (all test cases)
    :param max_points: Maximum score points (default 1.0)
    :param cpu_time_limit: Execution timeout in seconds
    :param memory_limit: Memory limit in KB
    :return: Full response dictionary adhering to docs/API.md
    """
    # 1. Parse test cases
    parsed_cases: List[TestCase] = []
    for idx, item in enumerate(test_cases_data):
        if isinstance(item, TestCase):
            parsed_cases.append(item)
        elif isinstance(item, dict):
            parsed_cases.append(TestCase.from_dict(item, default_id=idx + 1))

    # 2. Filter test cases if action is 'run' (sample/visible only)
    action_norm = action.strip().lower()
    if action_norm == "run":
        evaluation_cases = [tc for tc in parsed_cases if not tc.is_hidden]
        # If no visible cases defined, fall back to evaluating all
        if not evaluation_cases:
            evaluation_cases = parsed_cases
    else:
        evaluation_cases = parsed_cases

    # 3. Execute test cases
    eval_summary = run_test_cases(
        client=client,
        source_code=source_code,
        language=language,
        test_cases=evaluation_cases,
        cpu_time_limit=cpu_time_limit,
        memory_limit=memory_limit,
    )

    # 4. Compute score
    scoring = calculate_score(
        passed_count=eval_summary["passed_count"],
        total_count=eval_summary["total_count"],
        max_points=max_points,
    )

    # 5. Build standard API response
    overall_status = "success"
    if eval_summary["compilation_error"]:
        overall_status = "compilation_error"

    return {
        "status": overall_status,
        "action": action_norm,
        "language": language,
        "score": scoring["score"],
        "max_points": scoring["max_points"],
        "percentage": scoring["percentage"],
        "passed_count": scoring["passed_count"],
        "total_count": scoring["total_count"],
        "feedback": scoring["feedback"],
        "compilation_error": eval_summary["compilation_error"],
        "results": eval_summary["results"],
    }
