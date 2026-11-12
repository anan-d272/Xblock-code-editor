"""
Scoring logic for coding exam submissions.
Calculates earned points, percentages, and performance summaries based on test case evaluation.
"""
from typing import Any, Dict


def calculate_score(
    passed_count: int,
    total_count: int,
    max_points: float = 1.0,
) -> Dict[str, Any]:
    """
    Calculate submission score based on test cases passed.

    :param passed_count: Number of test cases passed (>= 0)
    :param total_count: Total number of test cases (>= 0)
    :param max_points: Maximum grade points possible (defaults to 1.0 for Open edX standard)
    :return: Dictionary with score, percentage, counts, and grade feedback
    """
    if total_count <= 0:
        return {
            "score": 0.0,
            "max_points": float(max_points),
            "percentage": 0.0,
            "passed_count": 0,
            "total_count": 0,
            "feedback": "No test cases configured.",
        }

    # Ensure counts are within valid bounds
    safe_passed = max(0, min(passed_count, total_count))
    ratio = safe_passed / total_count
    earned_score = round(ratio * float(max_points), 4)
    percentage = round(ratio * 100.0, 2)

    if safe_passed == total_count:
        feedback = f"All {total_count} test cases passed."
    elif safe_passed == 0:
        feedback = f"0 of {total_count} test cases passed."
    else:
        feedback = f"Passed {safe_passed} of {total_count} test cases ({percentage}%)."

    return {
        "score": earned_score,
        "max_points": float(max_points),
        "percentage": percentage,
        "passed_count": safe_passed,
        "total_count": total_count,
        "feedback": feedback,
    }

