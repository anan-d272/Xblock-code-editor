"""
Backend execution, grading, attempt storage, and integrity event handlers.
Provides reusable backend logic called by the Open edX CodingExamXBlock.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .client import Judge0Client
from .tester import run_submission

SUPPORTED_LANGUAGES = {"python", "java", "cpp"}
MAX_CODE_SIZE = 50_000  # characters

# Default test cases for initial units or when author has not defined custom ones
DEFAULT_TEST_CASES = [
    {
        "id": 1,
        "input": "10 20\n",
        "expected_output": "30",
        "is_hidden": False,
    },
    {
        "id": 2,
        "input": "5 -2\n",
        "expected_output": "3",
        "is_hidden": False,
    },
    {
        "id": 3,
        "input": "100 250\n",
        "expected_output": "350",
        "is_hidden": True,
    },
    {
        "id": 4,
        "input": "0 0\n",
        "expected_output": "0",
        "is_hidden": True,
    },
]


def get_block_test_cases(block: Any) -> List[Dict[str, Any]]:
    """Retrieve test cases configured on the XBlock or return sensible defaults."""
    custom_cases = getattr(block, "test_cases", None)
    if custom_cases and isinstance(custom_cases, list) and len(custom_cases) > 0:
        return custom_cases
    return DEFAULT_TEST_CASES


def validate_submission_payload(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate common payload parameters for run and submit."""
    language = data.get("language", "")
    code = data.get("code", "")

    if language not in SUPPORTED_LANGUAGES:
        return {"error": f"Unsupported language: {language!r}"}
    if not isinstance(code, str) or not code.strip():
        return {"error": "No code provided"}
    if len(code) > MAX_CODE_SIZE:
        return {"error": f"Code exceeds {MAX_CODE_SIZE} characters limit"}
    return None


def handle_run_request(
    block: Any,
    data: Dict[str, Any],
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Handle student 'Run' action:
    1. Validates source code and language.
    2. Filters to sample / visible test cases only.
    3. Executes code against execution client.
    4. Returns structured per-test-case results.
    *CRITICAL: Does NOT publish grades to Open edX.*
    """
    err = validate_submission_payload(data)
    if err:
        return err

    language = data["language"]
    code = data["code"]
    test_cases = get_block_test_cases(block)
    max_points = float(getattr(block, "max_points", 100.0) or 100.0)
    cpu_limit = getattr(block, "cpu_time_limit", None)
    mem_limit = getattr(block, "memory_limit", None)

    exec_client = client or Judge0Client()

    # Execute visible test cases only
    response = run_submission(
        client=exec_client,
        source_code=code,
        language=language,
        test_cases_data=test_cases,
        action="run",
        max_points=max_points,
        cpu_time_limit=cpu_limit,
        memory_limit=mem_limit,
    )

    return response


def handle_submit_request(
    block: Any,
    data: Dict[str, Any],
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Handle student 'Submit' action:
    1. Validates final code and language.
    2. Evaluates code against ALL test cases (visible and hidden).
    3. Calculates official problem score.
    4. Publishes grade to Open edX gradebook.
    5. Stores student attempt and last submission in user state.
    6. Masks hidden test case outputs before returning to frontend.
    """
    err = validate_submission_payload(data)
    if err:
        return err

    language = data["language"]
    code = data["code"]
    test_cases = get_block_test_cases(block)
    max_points = float(getattr(block, "max_points", 100.0) or 100.0)
    cpu_limit = getattr(block, "cpu_time_limit", None)
    mem_limit = getattr(block, "memory_limit", None)

    exec_client = client or Judge0Client()

    # Execute all test cases (both visible and hidden)
    response = run_submission(
        client=exec_client,
        source_code=code,
        language=language,
        test_cases_data=test_cases,
        action="submit",
        max_points=max_points,
        cpu_time_limit=cpu_limit,
        memory_limit=mem_limit,
    )

    earned_score = float(response["score"])

    # Publish grade event to Open edX runtime
    publish_xblock_grade(block, earned_score, max_points)

    # Persist attempt record in student user_state
    record_student_attempt(block, language, code, response)

    return response


def publish_xblock_grade(block: Any, score: float, max_points: float) -> bool:
    """
    Publish student grade event to the Open edX gradebook via the XBlock runtime.
    Ensures the score appears in Open edX Progress.
    """
    if hasattr(block, "runtime") and hasattr(block.runtime, "publish"):
        try:
            block.runtime.publish(
                block,
                "grade",
                {
                    "value": float(score),
                    "max_value": float(max_points),
                },
            )
            return True
        except Exception as exc:
            # Log error if runtime fails
            return False
    return False


def record_student_attempt(
    block: Any,
    language: str,
    code: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Store student submission details in Scope.user_state.
    Tracks attempt count, timestamps, score, and submission history.
    """
    current_attempts = int(getattr(block, "attempts", 0) or 0) + 1
    if hasattr(block, "attempts"):
        block.attempts = current_attempts

    user_id = "anonymous"
    if hasattr(block, "runtime") and hasattr(block.runtime, "user_id") and block.runtime.user_id:
        user_id = str(block.runtime.user_id)
    elif hasattr(block, "scope_ids") and hasattr(block.scope_ids, "user_id") and block.scope_ids.user_id:
        user_id = str(block.scope_ids.user_id)

    attempt_record = {
        "attempt_number": current_attempts,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "language": language,
        "code": code,
        "score": result.get("score", 0.0),
        "max_points": result.get("max_points", 100.0),
        "percentage": result.get("percentage", 0.0),
        "passed_count": result.get("passed_count", 0),
        "total_count": result.get("total_count", 0),
        "status": result.get("status", "unknown"),
    }

    if hasattr(block, "last_submission"):
        block.last_submission = attempt_record

    if hasattr(block, "submission_history"):
        history = list(getattr(block, "submission_history", []) or [])
        history.append(attempt_record)
        # Bound history to last 20 attempts
        block.submission_history = history[-20:]

    return attempt_record


# ------------------------------------------------------------------ #
# Day 6: Integrity Signals & Suspicious Activity Flags                #
# ------------------------------------------------------------------ #

DEFAULT_MAX_PASTE_THRESHOLD = 3
DEFAULT_LARGE_INSERTION_THRESHOLD = 150  # characters


def handle_integrity_event(block: Any, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Record integrity-related events sent by the student browser.
    Tracks paste attempts, sudden large code insertions, and updates suspicious flags.
    Does NOT automatically penalize students; flags evidence for instructor review.
    """
    event_type = str(data.get("event_type", "unknown")).strip()
    if event_type not in ("paste", "large_insertion"):
        return {
            "status": "error",
            "message": f"Invalid event_type '{event_type}'. Must be 'paste' or 'large_insertion'.",
        }

    raw_details = data.get("details", {})
    char_count = 0
    if "char_count" in data:
        try:
            char_count = int(data["char_count"])
        except (ValueError, TypeError):
            char_count = 0
    elif isinstance(raw_details, dict) and "char_count" in raw_details:
        try:
            char_count = int(raw_details["char_count"])
        except (ValueError, TypeError):
            char_count = 0

    language = str(data.get("language") or (raw_details.get("language") if isinstance(raw_details, dict) else "") or "")

    # 1. Update counters
    paste_count = int(getattr(block, "paste_count", 0) or 0)
    large_insertions = int(getattr(block, "large_insertions", 0) or 0)

    char_threshold = getattr(block, "large_insertion_threshold", DEFAULT_LARGE_INSERTION_THRESHOLD)

    if event_type == "paste":
        paste_count += 1
        if hasattr(block, "paste_count"):
            block.paste_count = paste_count

    if event_type == "large_insertion" or char_count >= char_threshold:
        large_insertions += 1
        if hasattr(block, "large_insertions"):
            block.large_insertions = large_insertions

    # 2. Build event record
    event_record = {
        "event_id": (len(getattr(block, "integrity_events", []) or []) + 1),
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "char_count": char_count,
        "language": language,
        "details": raw_details,
    }

    # 3. Append to user_state log
    if hasattr(block, "integrity_events"):
        events = list(getattr(block, "integrity_events", []) or [])
        events.append(event_record)
        block.integrity_events = events[-50:]  # keep last 50 events

    # 4. Check configurable thresholds
    max_pastes = getattr(block, "max_paste_threshold", DEFAULT_MAX_PASTE_THRESHOLD)
    max_large_insertions = getattr(block, "max_large_insertions_threshold", 2)

    is_flagged = bool(paste_count >= max_pastes or large_insertions >= max_large_insertions)
    if hasattr(block, "is_flagged"):
        block.is_flagged = is_flagged

    return {
        "status": "success",
        "event_type": event_type,
        "paste_count": paste_count,
        "large_insertions": large_insertions,
        "is_flagged": is_flagged,
        "message": "Integrity event recorded.",
    }


def get_integrity_summary(block: Any) -> Dict[str, Any]:
    """Retrieve instructor-facing integrity summary and audit trail for a student."""
    events = list(getattr(block, "integrity_events", []) or [])
    return {
        "status": "success",
        "is_flagged": bool(getattr(block, "is_flagged", False)),
        "paste_count": int(getattr(block, "paste_count", 0) or 0),
        "large_insertions": int(getattr(block, "large_insertions", 0) or 0),
        "total_events": len(events),
        "max_paste_threshold": getattr(block, "max_paste_threshold", DEFAULT_MAX_PASTE_THRESHOLD),
        "large_insertion_threshold": getattr(block, "large_insertion_threshold", DEFAULT_LARGE_INSERTION_THRESHOLD),
        "recent_events": events[-10:],
    }

