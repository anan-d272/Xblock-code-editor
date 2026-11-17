"""
Test Suite for Day 7 Tutor Plugin Packaging and Open edX Integration:
Verifies Tutor plugin recognition, XBlock registration, and end-to-end multi-language execution in Open edX.
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUTOR_BIN = "/home/teerth/tutor19-env/bin/tutor"


def test_tutor_plugin_recognition():
    print("[1/5] Testing Tutor recognizes and enables coding_exam plugin...")
    res = subprocess.run([TUTOR_BIN, "plugins", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, f"tutor plugins list failed: {res.stderr}"
    assert "coding_exam" in res.stdout, "coding_exam plugin not found in tutor plugins list"
    assert "✅ enabled" in res.stdout, "coding_exam plugin is not enabled in Tutor"
    print("      ✓ coding_exam is recognized as an enabled Tutor plugin")


def test_tutor_custom_cli_command():
    print("[2/5] Testing Tutor custom CLI command (tutor coding-exam status)...")
    res = subprocess.run([TUTOR_BIN, "coding-exam", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, f"tutor coding-exam status failed: {res.stderr}"
    assert "active" in res.stdout.lower() or "installed" in res.stdout.lower()
    print("      ✓ tutor coding-exam status command executed successfully")


def test_xblock_registered_in_openedx_containers():
    print("[3/5] Testing XBlock entry-point discovery inside Open edX LMS and Studio containers...")
    cmd_lms = [
        "docker", "exec", "tutor_local-lms-1", "python", "-c",
        "import pkg_resources; eps = [ep.name for ep in pkg_resources.iter_entry_points('xblock.v1')]; assert 'coding_exam' in eps"
    ]
    res_lms = subprocess.run(cmd_lms, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res_lms.returncode == 0, f"LMS registration check failed: {res_lms.stderr}"

    cmd_cms = [
        "docker", "exec", "tutor_local-cms-1", "python", "-c",
        "import pkg_resources; eps = [ep.name for ep in pkg_resources.iter_entry_points('xblock.v1')]; assert 'coding_exam' in eps"
    ]
    res_cms = subprocess.run(cmd_cms, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res_cms.returncode == 0, f"CMS registration check failed: {res_cms.stderr}"
    print("      ✓ coding_exam entry-point verified in both LMS and Studio (CMS)")


def test_openedx_multi_language_execution():
    print("[4/5] Testing Python, C++, and Java execution from inside Open edX container...")
    check_script = """
import json
from xblock.test.tools import TestRuntime
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds
from coding_exam.block import CodingExamXBlock
from unittest.mock import MagicMock
from webob import Request

field_data = DictFieldData({})
runtime = TestRuntime(services={'user': MagicMock(), 'field-data': field_data})
published = []
runtime.publish = lambda b, evt, data: published.append((evt, data))

scope_ids = ScopeIds('user1', 'coding_exam', 'def1', 'usage1')
block = runtime.construct_xblock_from_class(CodingExamXBlock, scope_ids)
block.allowed_languages = ['python', 'cpp', 'java']

# Python
py_code = 'a = int(input())\\nb = int(input())\\nprint(a + b)'
req_py = Request.blank('/', method='POST', body=json.dumps({'language': 'python', 'code': py_code}).encode('utf-8'), content_type='application/json')
res_py = json.loads(block.submit_code(req_py).body.decode('utf-8'))
assert res_py['score'] == 10.0, f'Python failed: {res_py}'

# C++
cpp_code = '#include <iostream>\\nusing namespace std;\\nint main() { int a, b; if (cin >> a >> b) cout << a + b << endl; return 0; }'
req_cpp = Request.blank('/', method='POST', body=json.dumps({'language': 'cpp', 'code': cpp_code}).encode('utf-8'), content_type='application/json')
res_cpp = json.loads(block.submit_code(req_cpp).body.decode('utf-8'))
assert res_cpp['score'] == 10.0, f'C++ failed: {res_cpp}'

# Java
java_code = 'import java.util.Scanner;\\npublic class Main { public static void main(String[] args) { Scanner sc = new Scanner(System.in); if (sc.hasNextInt()) { int a = sc.nextInt(); int b = sc.nextInt(); System.out.println(a + b); } } }'
req_java = Request.blank('/', method='POST', body=json.dumps({'language': 'java', 'code': java_code}).encode('utf-8'), content_type='application/json')
res_java = json.loads(block.submit_code(req_java).body.decode('utf-8'))
assert res_java['score'] == 10.0, f'Java failed: {res_java}'

print('OK')
"""
    cmd = ["docker", "exec", "tutor_local-lms-1", "python", "-c", check_script]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, f"Multi-language execution failed: {res.stderr}\n{res.stdout}"
    print("      ✓ Python, C++, and Java successfully executed through XBlock in Open edX")


def test_run_vs_submit_grading_integrity():
    print("[5/5] Testing Run (no grade) vs Submit (grade published & attempt incremented)...")
    integrity_script = """
import json
from xblock.test.tools import TestRuntime
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds
from coding_exam.block import CodingExamXBlock
from unittest.mock import MagicMock
from webob import Request

field_data = DictFieldData({})
runtime = TestRuntime(services={'user': MagicMock(), 'field-data': field_data})
published = []
runtime.publish = lambda b, evt, data: published.append((evt, data))

scope_ids = ScopeIds('student101', 'coding_exam', 'def1', 'usage1')
block = runtime.construct_xblock_from_class(CodingExamXBlock, scope_ids)

code = 'a = int(input())\\nb = int(input())\\nprint(a + b)'
req_run = Request.blank('/', method='POST', body=json.dumps({'language': 'python', 'code': code}).encode('utf-8'), content_type='application/json')
run_data = json.loads(block.run_code(req_run).body.decode('utf-8'))
assert run_data['passed_count'] == 1
assert len(published) == 0, 'Run handler published a grade!'
assert block.attempts == 0

req_sub = Request.blank('/', method='POST', body=json.dumps({'language': 'python', 'code': code}).encode('utf-8'), content_type='application/json')
sub_data = json.loads(block.submit_code(req_sub).body.decode('utf-8'))
assert sub_data['score'] == 10.0
assert len(published) == 1, 'Submit handler did not publish grade!'
assert published[0][1]['value'] == 10.0
assert block.attempts == 1

print('OK')
"""
    cmd = ["docker", "exec", "tutor_local-lms-1", "python", "-c", integrity_script]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, f"Grading integrity check failed: {res.stderr}\n{res.stdout}"
    print("      ✓ Gradebook publication and attempt limits strictly verified")


if __name__ == "__main__":
    print("===================================================================")
    print("          DAY 7 TUTOR PLUGIN & OPEN EDX VERIFICATION               ")
    print("===================================================================")
    try:
        test_tutor_plugin_recognition()
        test_tutor_custom_cli_command()
        test_xblock_registered_in_openedx_containers()
        test_openedx_multi_language_execution()
        test_run_vs_submit_grading_integrity()
        print("===================================================================")
        print("             ALL DAY 7 TESTS PASSED SUCCESSFULLY!                  ")
        print("===================================================================")
    except AssertionError as e:
        print(f"\n[FAIL] Test assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        sys.exit(1)
