"""
Test Suite for Day 6 Backend Development:
Integrity Signals, Anti-Cheating Tracking, Suspicious Flags, and Docker Sandbox Hardening.
"""
import os
import sys
import glob
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
    handle_integrity_event,
    get_integrity_summary,
)


class MockBlockState:
    """Mock XBlock instance holding integrity and suspicious activity fields."""
    def __init__(self, max_paste_threshold=3, max_large_insertions_threshold=2, large_insertion_threshold=100):
        self.max_paste_threshold = max_paste_threshold
        self.max_large_insertions_threshold = max_large_insertions_threshold
        self.large_insertion_threshold = large_insertion_threshold
        self.integrity_events = []
        self.paste_count = 0
        self.large_insertions = 0
        self.is_flagged = False


def test_integrity_event_recording():
    print("[1/5] Testing integrity event recording and counter tracking...")
    block = MockBlockState(max_paste_threshold=3, max_large_insertions_threshold=2, large_insertion_threshold=100)

    # 1. Report small paste event (< 100 chars)
    payload1 = {
        "event_type": "paste",
        "char_count": 35,
        "language": "python",
        "details": "Small snippet paste",
    }
    res1 = handle_integrity_event(block, payload1)
    assert res1["status"] == "success"
    assert block.paste_count == 1
    assert block.large_insertions == 0
    assert block.is_flagged is False
    assert len(block.integrity_events) == 1
    assert block.integrity_events[0]["event_type"] == "paste"
    assert block.integrity_events[0]["char_count"] == 35

    # 2. Report large insertion (> 100 chars)
    payload2 = {
        "event_type": "large_insertion",
        "char_count": 250,
        "language": "python",
        "details": "Pasted full function",
    }
    res2 = handle_integrity_event(block, payload2)
    assert res2["status"] == "success"
    assert block.large_insertions == 1
    assert block.is_flagged is False
    assert len(block.integrity_events) == 2

    # 3. Report invalid event type
    res_err = handle_integrity_event(block, {"event_type": "unknown_action"})
    assert res_err["status"] == "error"
    assert "Invalid event_type" in res_err["message"]

    print("      ✓ Integrity events safely validated and recorded")


def test_suspicious_activity_threshold_flagging():
    print("[2/5] Testing threshold-based suspicious activity flags...")
    block = MockBlockState(max_paste_threshold=3, max_large_insertions_threshold=2, large_insertion_threshold=100)

    # Trigger paste events up to threshold
    handle_integrity_event(block, {"event_type": "paste", "char_count": 20})
    handle_integrity_event(block, {"event_type": "paste", "char_count": 30})
    assert block.is_flagged is False

    # 3rd paste hits threshold (>= 3)
    res = handle_integrity_event(block, {"event_type": "paste", "char_count": 40})
    assert block.is_flagged is True
    assert res["is_flagged"] is True

    # Check Instructor Audit Summary
    summary = get_integrity_summary(block)
    assert summary["status"] == "success"
    assert summary["is_flagged"] is True
    assert summary["paste_count"] == 3
    assert summary["max_paste_threshold"] == 3
    assert len(summary["recent_events"]) == 3
    print("      ✓ Student attempt flagged on paste threshold and instructor summary generated")


def test_large_insertion_threshold_flagging():
    print("[3/5] Testing large insertion threshold flagging...")
    block = MockBlockState(max_paste_threshold=10, max_large_insertions_threshold=2, large_insertion_threshold=100)

    # 1st large insertion (char_count >= 100)
    handle_integrity_event(block, {"event_type": "paste", "char_count": 150})
    assert block.large_insertions == 1
    assert block.is_flagged is False

    # 2nd large insertion hits threshold
    res = handle_integrity_event(block, {"event_type": "large_insertion", "char_count": 300})
    assert block.large_insertions == 2
    assert block.is_flagged is True
    assert res["is_flagged"] is True
    print("      ✓ Student attempt flagged on large code insertion threshold")


def test_docker_sandbox_output_truncation_hardening():
    print("[4/5] Testing Docker sandbox output size restriction (1MB cap)...")
    client = DockerSandboxClient(max_output_bytes=500)

    # Python program generating 50,000 characters
    flood_code = "print('A' * 50000)"
    res = client.execute(flood_code, "python")
    
    # Output should be clamped to at most 500 bytes without crashing host
    assert len(res.stdout) <= 500
    print(f"      ✓ Sandboxed output strictly capped (stdout length: {len(res.stdout)} <= 500 bytes)")


def test_docker_sandbox_security_isolation_and_cleanup():
    print("[5/5] Testing Docker container non-root execution and host file cleanup...")
    client = DockerSandboxClient()

    # 1. Verify container executes as non-root user (UID 1001)
    uid_check_code = """
import os
print(f"UID:{os.getuid()},GID:{os.getgid()}")
"""
    res_uid = client.execute(uid_check_code, "python")
    assert res_uid.is_success is True
    assert "UID:1001,GID:1001" in res_uid.stdout.strip()

    # 2. Verify network isolation inside container
    net_check_code = """
import socket
try:
    s = socket.create_connection(("8.8.8.8", 53), timeout=1)
    print("NET_OPEN")
except Exception as e:
    print(f"NET_BLOCKED:{type(e).__name__}")
"""
    res_net = client.execute(net_check_code, "python")
    assert "NET_BLOCKED" in res_net.stdout

    # 3. Verify temporary host directories are cleaned up
    leftovers = glob.glob("/tmp/xblock_sandbox_*")
    assert len(leftovers) == 0, f"Found leaked temporary directories: {leftovers}"

    print("      ✓ Non-root UID 1001 verified, network blocked, and 0 leaked temporary directories")


if __name__ == "__main__":
    print("===================================================================")
    print("       DAY 6 INTEGRITY SIGNALS & SANDBOX HARDENING AUDIT           ")
    print("===================================================================")
    try:
        test_integrity_event_recording()
        test_suspicious_activity_threshold_flagging()
        test_large_insertion_threshold_flagging()
        test_docker_sandbox_output_truncation_hardening()
        test_docker_sandbox_security_isolation_and_cleanup()
        print("===================================================================")
        print("             ALL DAY 6 TESTS PASSED SUCCESSFULLY!                  ")
        print("===================================================================")
    except AssertionError as e:
        print(f"\n[FAIL] Test assertion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error during tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

