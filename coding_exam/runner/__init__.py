"""
Runner package for the Open edX Coding Exam XBlock.
Contains the execution client, test-case evaluator, and scoring engine.
"""
from .client import ExecutionResult, Judge0Client
from .scoring import calculate_score
from .tester import TestCase, TestCaseResult, normalize_output, run_test_cases

__all__ = [
    "Judge0Client",
    "ExecutionResult",
    "TestCase",
    "TestCaseResult",
    "normalize_output",
    "run_test_cases",
    "calculate_score",
]
