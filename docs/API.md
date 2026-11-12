# API Contract: Coding Exam XBlock & Runner

This document outlines the API contract between the **Frontend (XBlock View & Handlers)** and the **Backend (Execution Runner & Scoring Engine)**.

---

## 1. Overview & Action Types

The XBlock exposes two main actions to students:

1. **`run` (Test Run):**
   - Runs code against **sample / visible test cases** only.
   - Used by the student for fast feedback and iterative debugging.
   - Does **not** record official grades or modify student state in Open edX.

2. **`submit` (Exam Submission):**
   - Runs code against **all test cases** (both visible and hidden).
   - Generates the official score and persists student grades to the Open edX gradebook.

---

## 2. Request Specification

When a student clicks **Run** or **Submit**, the frontend sends a `POST` JSON request to the corresponding XBlock handler (e.g. `run_code` or `submit_code`).

### Request Payload Format

```json
{
  "action": "run",
  "language": "python",
  "code": "a = int(input())\nb = int(input())\nprint(a + b)"
}
```

### Request Fields

| Field | Type | Required | Allowed Values | Description |
| :--- | :--- | :--- | :--- | :--- |
| `action` | `string` | Yes | `"run"`, `"submit"` | Action being triggered. |
| `language` | `string` | Yes | `"python"`, `"cpp"`, `"c++"`, `"java"` | Target programming language. |
| `code` | `string` | Yes | *Source code string* | Student's submitted source code. |

---

## 3. Response Specification

The backend evaluates the submission and returns a standard JSON response structure.

### A. Success Response (`200 OK`) — All Test Cases Run

```json
{
  "status": "success",
  "action": "submit",
  "language": "python",
  "score": 0.8,
  "max_points": 1.0,
  "percentage": 80.0,
  "passed_count": 4,
  "total_count": 5,
  "feedback": "Passed 4 of 5 test cases (80.0%).",
  "compilation_error": null,
  "results": [
    {
      "test_case_id": 1,
      "passed": true,
      "is_hidden": false,
      "input": "10\n20",
      "expected_output": "30",
      "actual_output": "30",
      "status": "PASSED",
      "error_message": "",
      "execution_time": 0.012
    },
    {
      "test_case_id": 2,
      "passed": false,
      "is_hidden": false,
      "input": "5\n-2",
      "expected_output": "3",
      "actual_output": "7",
      "status": "WRONG_ANSWER",
      "error_message": "Output did not match expected output.",
      "execution_time": 0.011
    },
    {
      "test_case_id": 3,
      "passed": false,
      "is_hidden": true,
      "input": "[Hidden]",
      "expected_output": "[Hidden]",
      "actual_output": "[Hidden]",
      "status": "WRONG_ANSWER",
      "error_message": "Output did not match expected output.",
      "execution_time": 0.015
    }
  ]
}
```

### B. Compilation Error Response (`200 OK` with compilation details)

If the student's code has compilation errors (C++ or Java), execution is halted early to conserve resources:

```json
{
  "status": "compilation_error",
  "action": "submit",
  "language": "cpp",
  "score": 0.0,
  "max_points": 1.0,
  "percentage": 0.0,
  "passed_count": 0,
  "total_count": 3,
  "feedback": "0 of 3 test cases passed.",
  "compilation_error": "main.cpp: In function 'int main()':\nmain.cpp:2:14: error: 'broken_syntax' was not declared in this scope",
  "results": [
    {
      "test_case_id": 1,
      "passed": false,
      "is_hidden": false,
      "input": "10\n20",
      "expected_output": "30",
      "actual_output": "",
      "status": "COMPILATION_ERROR",
      "error_message": "main.cpp: In function 'int main()':\nmain.cpp:2:14: error: 'broken_syntax' was not declared in this scope",
      "execution_time": 0.0
    },
    {
      "test_case_id": 2,
      "passed": false,
      "is_hidden": false,
      "input": "5\n-2",
      "expected_output": "3",
      "actual_output": "",
      "status": "SKIPPED",
      "error_message": "Skipped due to previous compilation error.",
      "execution_time": 0.0
    }
  ]
}
```

### C. Runtime Error / Timeout in Individual Test Cases

When a test case fails due to an unhandled exception or timeout:
- `status`: `"RUNTIME_ERROR"` or `"TIME_LIMIT_EXCEEDED"`.
- `error_message`: Contains standard error message (e.g., `ZeroDivisionError`, `NullPointerException`, or `Time limit exceeded (2.0s)`).

---

## 4. Test Case Masking for Hidden Test Cases

To preserve exam integrity:
- If a test case has `"is_hidden": true`:
  - Its `input` and `expected_output` are masked as `"[Hidden]"`.
  - If it fails, its `actual_output` is also masked as `"[Hidden]"`.
  - The student is only shown whether the hidden test case `passed` (true/false) and the status.

---

## 5. Supported Language Identifiers

| Language | Identifier (`language` field) | Judge0 ID | Compiler / Runtime |
| :--- | :--- | :--- | :--- |
| **Python** | `"python"`, `"python3"`, `"py"` | 71 | Python 3.8.1 |
| **C++** | `"cpp"`, `"c++"` | 54 | GCC 9.2.0 |
| **Java** | `"java"` | 62 | OpenJDK 13.0.1 (Class must be `public class Main`) |
