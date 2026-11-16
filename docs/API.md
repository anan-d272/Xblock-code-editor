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

---

## 6. Open edX Gradebook Publishing Contract

Official grading is exclusively triggered when the student executes `submit_code`. The `run_code` action **never** publishes grades.

### Grade Publishing Mechanism

The XBlock declares `has_score = True` and defines `max_score()` returning `self.max_points`. During `submit_code`, the backend invokes:

```python
self.runtime.publish(
    self,
    "grade",
    {
        "value": round(score, 2),
        "max_value": float(max_points),
    }
)
```

### Grade Calculation Formula

$$\text{Score} = \left(\frac{\text{Passed Test Cases}}{\text{Total Test Cases}}\right) \times \text{Maximum Problem Points}$$

- Total test cases include both visible and hidden test cases.
- If total test cases is 0 or compilation fails, score published is `0.0`.
- Scores are published as floating-point values rounded to two decimal places.

---

## 7. Student Attempt & Submission History Storage

Student submissions are persisted in `Scope.user_state` so they are scoped per learner per problem unit.

### Data Model

1. **`attempts` (`Integer`, default `0`):** Number of official exam submissions made by the student.
2. **`last_submission` (`Dict`, default `{}`):** Snapshot of the most recent evaluation:
   ```json
   {
     "attempt_number": 1,
     "timestamp": "2026-11-16T12:00:00Z",
     "user_id": "student_101",
     "language": "python",
     "score": 80.0,
     "max_points": 100.0,
     "percentage": 80.0,
     "passed_count": 4,
     "total_count": 5,
     "status": "success",
     "results": [ ... ]
   }
   ```
3. **`submission_history` (`List[Dict]`, default `[]`):** Chronological log of the student's submissions (bounded to the last 10 attempts to optimize state storage).

### Endpoint: `get_submission_history`

- **Method:** `POST` / `GET` JSON handler.
- **Response:**
  ```json
  {
    "status": "success",
    "attempts": 2,
    "last_submission": { ... },
    "submission_history": [ ... ]
  }
  ```

---

## 8. Integrity & Anti-Cheating Event Tracking

To monitor academic integrity during online exams, the XBlock tracks clipboard activity, paste events, and abnormal code volume insertions.

### Endpoint: `report_integrity`

Frontend event listeners (such as CodeMirror paste hooks) post integrity events to this endpoint.

#### Request Payload
```json
{
  "event_type": "paste",
  "char_count": 142,
  "language": "python",
  "details": "Pasted 142 characters into editor"
}
```

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `event_type` | `string` | Yes | `"paste"` or `"large_insertion"` |
| `char_count` | `integer` | No | Number of characters inserted (default `0`) |
| `language` | `string` | No | Programming language active in editor |
| `details` | `string` | No | Diagnostic context or frontend note |

#### Response (`200 OK`)
```json
{
  "status": "success",
  "paste_count": 3,
  "large_insertions": 1,
  "is_flagged": false,
  "message": "Integrity event recorded."
}
```

### Suspicious Activity Thresholds & Instructor Flags

The XBlock tracks:
- `paste_count` (`Integer`): Cumulative number of paste actions.
- `large_insertions` (`Integer`): Cumulative insertions with `char_count >= 100`.
- `is_flagged` (`Boolean`): Set to `true` when:
  - `paste_count >= max_paste_threshold` (default `3`), OR
  - `large_insertions >= large_insertion_threshold` (default `2`).

### Endpoint: `get_integrity_summary`

Provides instructors with an audit summary of the learner's session:

```json
{
  "status": "success",
  "is_flagged": true,
  "paste_count": 4,
  "large_insertions": 2,
  "total_events": 6,
  "max_paste_threshold": 3,
  "large_insertion_threshold": 2,
  "recent_events": [
    {
      "event_type": "paste",
      "char_count": 120,
      "language": "python",
      "timestamp": "2026-11-16T12:05:00+00:00"
    }
  ]
}
```

---

## 9. Docker Sandbox Hardening & Security Guarantees

When local execution is used (via `coding-exam-sandbox:latest` / `DockerSandboxClient`), untrusted student code is isolated with multi-layer host defenses:

1. **Zero Network Connectivity (`--network none`):**
   - Socket creation to loopback or external addresses is blocked at kernel level.
   - Prevents outbound data exfiltration and credential leaks.

2. **Unprivileged Container User (`--user 1001:1001`):**
   - Runs as non-root user `sandboxuser`.
   - Cannot modify system files or mount paths.

3. **Read-Only Volume Mounts (`:ro`):**
   - The student source directory on the host is mounted read-only.
   - Scratch writes occur only in ephemeral `/sandbox_run`.

4. **Strict CPU & Memory Limits:**
   - `--cpus 0.5`: Enforces hard CFS quota to prevent CPU starvation.
   - `-m 128m`: Enforces kernel cgroup memory limits to prevent host OOM.

5. **Output Size Clamping (`head -c 1048576`):**
   - Standard output is piped through `head -c 1048576` (1MB limit).
   - If code executes an infinite print loop, the pipe closes, sending `SIGPIPE` / `BrokenPipeError` to terminate the process before host disk or memory buffers fill up.

6. **Process Kill Timeout:**
   - Linux `timeout -s SIGKILL` ensures unresponsive tasks are forcefully destroyed after the configured timeout.

