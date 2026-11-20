"""
Day 6 Unit Tests — Editor Clipboard/Drop Protection and Integrity Event Logging.

Tests:
  1. Unknown event types are silently rejected
  2. Event cap: list never exceeds MAX_INTEGRITY_EVENTS
  3. Rate limit: extra events in a single POST are truncated to MAX_EVENTS_PER_POST
  4. Valid events increment integrity_counts correctly
  5. Non-dict events in a list are silently ignored
  6. Single event dict accepted
"""

import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class _Scope:
    settings   = "settings"
    user_state = "user_state"


class _FieldDescriptor:
    def __init__(self, default):
        self._default = default
        self._attr    = None

    def __set_name__(self, owner, name):
        self._attr = "_field_" + name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self._attr, self._default)

    def __set__(self, obj, value):
        setattr(obj, self._attr, value)


def _make_field(default):
    return _FieldDescriptor(default)

def String(default="", **kw):     return _make_field(default)
def Float(default=0.0, **kw):     return _make_field(default)
def Integer(default=0, **kw):     return _make_field(default)
def Boolean(default=False, **kw): return _make_field(default)
def List(default=None, **kw):     return _make_field(default if default is not None else [])
def Dict(default=None, **kw):     return _make_field(default if default is not None else {})

class Scope:
    settings   = _Scope.settings
    user_state = _Scope.user_state

class Fragment:
    def __init__(self, content=""):
        self.content = content
    def add_css(self, _):        pass
    def add_javascript(self, _): pass
    def initialize_js(self, _):  pass

class XBlock:
    @staticmethod
    def json_handler(fn):
        return fn


_MOCK_MODULE_KEYS = [
    "web_fragments", "web_fragments.fragment",
    "xblock", "xblock.core", "xblock.fields",
    "coding_exam", "coding_exam.block", "coding_exam.runner",
]

blk = None  # filled in by setUpModule


def setUpModule():
    """Install lightweight mock stubs so block.py can be imported without Open edX."""
    global blk
    for key in _MOCK_MODULE_KEYS:
        sys.modules.pop(key, None)

    wf_mod = types.ModuleType("web_fragments")
    wf_frag_mod = types.ModuleType("web_fragments.fragment")
    wf_frag_mod.Fragment = Fragment
    sys.modules["web_fragments"] = wf_mod
    sys.modules["web_fragments.fragment"] = wf_frag_mod

    xblock_mod = types.ModuleType("xblock")
    xblock_core_mod = types.ModuleType("xblock.core")
    xblock_core_mod.XBlock = XBlock
    sys.modules["xblock"] = xblock_mod
    sys.modules["xblock.core"] = xblock_core_mod

    xblock_fields_mod = types.ModuleType("xblock.fields")
    xblock_fields_mod.String  = String
    xblock_fields_mod.Float   = Float
    xblock_fields_mod.Integer = Integer
    xblock_fields_mod.Boolean = Boolean
    xblock_fields_mod.List    = List
    xblock_fields_mod.Dict    = Dict
    xblock_fields_mod.Scope   = Scope
    sys.modules["xblock.fields"] = xblock_fields_mod

    import importlib
    import coding_exam.block
    importlib.reload(coding_exam.block)
    blk = coding_exam.block


def tearDownModule():
    """Remove mock stubs so subsequent test modules start clean."""
    for key in _MOCK_MODULE_KEYS:
        sys.modules.pop(key, None)


def _make_block(integrity_events=None, integrity_counts=None):
    b = blk.CodingExamXBlock.__new__(blk.CodingExamXBlock)
    b.runtime          = MagicMock()
    b.integrity_events = list(integrity_events or [])
    b.integrity_counts = dict(integrity_counts or {})
    return b


class TestIntegrityEventLogging(unittest.TestCase):

    def test_unknown_event_types_are_rejected(self):
        b = _make_block()
        result = b.log_integrity_event([
            {"event_type": "unknown_type", "timestamp": "2024-01-01T00:00:00Z", "metadata": {}},
        ])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(b.integrity_events), 0)
        self.assertEqual(b.integrity_counts, {})

    def test_valid_events_are_stored_and_counted(self):
        b = _make_block()
        result = b.log_integrity_event([
            {"event_type": "paste_attempt", "timestamp": "2024-01-01T00:00:00Z", "metadata": {}},
            {"event_type": "copy_attempt",  "timestamp": "2024-01-01T00:00:01Z", "metadata": {}},
            {"event_type": "paste_attempt", "timestamp": "2024-01-01T00:00:02Z", "metadata": {}},
        ])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(b.integrity_events), 3)
        self.assertEqual(b.integrity_counts["paste_attempt"], 2)
        self.assertEqual(b.integrity_counts["copy_attempt"],  1)

    def test_event_log_capped_at_max(self):
        b = _make_block(
            integrity_events=[
                {"event_type": "paste_attempt", "timestamp": "t", "metadata": {}}
                for _ in range(blk.MAX_INTEGRITY_EVENTS - 1)
            ],
            integrity_counts={"paste_attempt": blk.MAX_INTEGRITY_EVENTS - 1},
        )
        b.log_integrity_event([
            {"event_type": "paste_attempt", "timestamp": "t2", "metadata": {}},
            {"event_type": "paste_attempt", "timestamp": "t3", "metadata": {}},
            {"event_type": "paste_attempt", "timestamp": "t4", "metadata": {}},
        ])
        self.assertLessEqual(len(b.integrity_events), blk.MAX_INTEGRITY_EVENTS)

    def test_rate_limit_per_post(self):
        b = _make_block()
        events = [
            {"event_type": "paste_attempt", "timestamp": "t", "metadata": {}}
            for _ in range(blk.MAX_EVENTS_PER_POST + 5)
        ]
        b.log_integrity_event(events)
        self.assertLessEqual(len(b.integrity_events), blk.MAX_EVENTS_PER_POST)

    def test_non_dict_events_are_ignored(self):
        b = _make_block()
        result = b.log_integrity_event(["not_a_dict", 42, None,
                                        {"event_type": "cut_attempt", "timestamp": "t", "metadata": {}}])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(b.integrity_events), 1)
        self.assertEqual(b.integrity_counts.get("cut_attempt"), 1)

    def test_single_event_dict_accepted(self):
        b = _make_block()
        result = b.log_integrity_event({"event_type": "drop_attempt", "timestamp": "t", "metadata": {}})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(b.integrity_events), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
