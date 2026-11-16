"""
Runner package for the Open edX Coding Exam XBlock.
Contains the execution clients (Judge0 and Docker Sandbox), test-case evaluator,
scoring engine, and XBlock integration handlers.
"""
from .client import ExecutionResult, Judge0Client
from .docker_client import DockerSandboxClient
from .handlers import (
    DEFAULT_TEST_CASES,
    get_integrity_summary,
    handle_integrity_event,
    handle_run_request,
    handle_submit_request,
    publish_xblock_grade,
    record_student_attempt,
)
from .scoring import calculate_score
from .tester import (
    TestCase,
    TestCaseResult,
    normalize_output,
    run_submission,
    run_test_cases,
)

__all__ = [
    "Judge0Client",
    "DockerSandboxClient",
    "ExecutionResult",
    "TestCase",
    "TestCaseResult",
    "normalize_output",
    "run_test_cases",
    "run_submission",
    "calculate_score",
    "DEFAULT_TEST_CASES",
    "handle_run_request",
    "handle_submit_request",
    "publish_xblock_grade",
    "record_student_attempt",
    "handle_integrity_event",
    "get_integrity_summary",
]
