"""
Execution client for dispatching student code to the Judge0 REST API.
Handles base64 encoding/decoding, language mapping, resource limits, result polling, and error handling.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ExecutionResult:
    """Standardized result returned from code execution."""
    status: str
    is_success: bool
    stdout: str
    stderr: str
    compile_output: str
    execution_time: float
    memory: int
    status_id: int
    status_description: str
    message: str = ""
    token: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "status": self.status,
            "is_success": self.is_success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "compile_output": self.compile_output,
            "execution_time": self.execution_time,
            "memory": self.memory,
            "status_id": self.status_id,
            "status_description": self.status_description,
            "message": self.message,
            "token": self.token,
        }


class Judge0Client:
    """Client for executing code against a Judge0 CE API instance with polling support."""

    # Default Judge0 Language IDs verified against Judge0 CE
    DEFAULT_LANGUAGE_MAP = {
        "python": int(os.environ.get("JUDGE0_PYTHON_ID", 71)),   # Python (3.8.1)
        "python3": int(os.environ.get("JUDGE0_PYTHON_ID", 71)),
        "py": int(os.environ.get("JUDGE0_PYTHON_ID", 71)),
        "cpp": int(os.environ.get("JUDGE0_CPP_ID", 54)),         # C++ (GCC 9.2.0)
        "c++": int(os.environ.get("JUDGE0_CPP_ID", 54)),
        "java": int(os.environ.get("JUDGE0_JAVA_ID", 62)),       # Java (OpenJDK 13.0.1)
    }

    # Judge0 Status ID to normalized status mapping
    STATUS_MAP = {
        1: "IN_QUEUE",
        2: "PROCESSING",
        3: "ACCEPTED",
        4: "WRONG_ANSWER",
        5: "TIME_LIMIT_EXCEEDED",
        6: "COMPILATION_ERROR",
        7: "RUNTIME_ERROR",       # SIGSEGV
        8: "RUNTIME_ERROR",       # SIGXFSZ
        9: "RUNTIME_ERROR",       # SIGFPE
        10: "RUNTIME_ERROR",      # SIGABRT
        11: "RUNTIME_ERROR",      # NZEC
        12: "RUNTIME_ERROR",      # Other
        13: "INTERNAL_ERROR",
        14: "EXEC_FORMAT_ERROR",
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        user_agent: str = "OpenEdX-CodingExam/1.0",
        timeout: int = 30,
        default_cpu_time_limit: float = 5.0,
        default_memory_limit: int = 128000,
    ):
        """
        Initialize the Judge0 client.

        :param base_url: Judge0 API base URL (defaults to JUDGE0_URL env var or public CE)
        :param user_agent: User-Agent header (required to prevent Cloudflare blocks)
        :param timeout: HTTP request timeout in seconds
        :param default_cpu_time_limit: Default execution time limit in seconds
        :param default_memory_limit: Default memory limit in kilobytes
        """
        self.base_url = (base_url or os.environ.get("JUDGE0_URL", "https://ce.judge0.com")).rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout
        self.default_cpu_time_limit = default_cpu_time_limit
        self.default_memory_limit = default_memory_limit

    @staticmethod
    def _b64_encode(text: Optional[str]) -> str:
        """Base64-encode a text string."""
        if text is None:
            return ""
        return base64.b64encode(text.encode("utf-8")).decode("utf-8")

    @staticmethod
    def _b64_decode(encoded_text: Optional[str]) -> str:
        """Base64-decode an API response field safely."""
        if not encoded_text:
            return ""
        try:
            return base64.b64decode(encoded_text.encode("utf-8")).decode("utf-8", errors="replace")
        except Exception:
            return encoded_text

    def get_language_id(self, language: str) -> int:
        """Resolve a programming language name to its Judge0 ID."""
        normalized = language.strip().lower()
        if normalized not in self.DEFAULT_LANGUAGE_MAP:
            supported = ", ".join(sorted(set(self.DEFAULT_LANGUAGE_MAP.keys())))
            raise ValueError(f"Unsupported language '{language}'. Supported languages: {supported}")
        return self.DEFAULT_LANGUAGE_MAP[normalized]

    def _parse_response(self, resp_json: Dict[str, Any], fallback_token: str = "") -> ExecutionResult:
        """Parse and decode response dictionary into an ExecutionResult."""
        token = resp_json.get("token") or fallback_token
        status_info = resp_json.get("status", {})
        status_id = status_info.get("id", 0)
        status_desc = status_info.get("description", "Unknown")

        # If status is not provided (e.g. initial token returned by async POST)
        if not status_info and token:
            normalized_status = "IN_QUEUE"
            status_id = 1
            status_desc = "In Queue"
        else:
            normalized_status = self.STATUS_MAP.get(status_id, "UNKNOWN")

        is_success = (status_id == 3)

        raw_time = resp_json.get("time")
        try:
            exec_time = float(raw_time) if raw_time is not None else 0.0
        except (ValueError, TypeError):
            exec_time = 0.0

        raw_memory = resp_json.get("memory")
        try:
            memory = int(raw_memory) if raw_memory is not None else 0
        except (ValueError, TypeError):
            memory = 0

        stdout = self._b64_decode(resp_json.get("stdout"))
        stderr = self._b64_decode(resp_json.get("stderr"))
        compile_output = self._b64_decode(resp_json.get("compile_output"))
        message = self._b64_decode(resp_json.get("message"))

        return ExecutionResult(
            status=normalized_status,
            is_success=is_success,
            stdout=stdout,
            stderr=stderr,
            compile_output=compile_output,
            execution_time=exec_time,
            memory=memory,
            status_id=status_id,
            status_description=status_desc,
            message=message,
            token=token,
        )

    def get_submission(self, token: str) -> ExecutionResult:
        """
        Retrieve result of a previously submitted execution by token.

        :param token: Judge0 submission UUID token
        :return: ExecutionResult object
        """
        endpoint = f"{self.base_url}/submissions/{token}?base64_encoded=true"
        req = urllib.request.Request(
            endpoint,
            headers={
                "User-Agent": self.user_agent,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
            return self._parse_response(resp_json, fallback_token=token)
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            return ExecutionResult(
                status="HTTP_ERROR",
                is_success=False,
                stdout="",
                stderr=f"HTTP Error {err.code}: {err.reason}",
                compile_output="",
                execution_time=0.0,
                memory=0,
                status_id=0,
                status_description=f"HTTP {err.code}",
                message=err_body,
                token=token,
            )
        except urllib.error.URLError as err:
            return ExecutionResult(
                status="CONNECTION_ERROR",
                is_success=False,
                stdout="",
                stderr=f"Failed to connect to execution server: {err.reason}",
                compile_output="",
                execution_time=0.0,
                memory=0,
                status_id=0,
                status_description="Connection Error",
                message=str(err),
                token=token,
            )
        except Exception as err:
            return ExecutionResult(
                status="INTERNAL_ERROR",
                is_success=False,
                stdout="",
                stderr=str(err),
                compile_output="",
                execution_time=0.0,
                memory=0,
                status_id=0,
                status_description="Internal Error",
                message=str(err),
                token=token,
            )

    def poll_submission(
        self,
        token: str,
        max_polls: int = 20,
        poll_interval: float = 0.5,
    ) -> ExecutionResult:
        """
        Poll Judge0 until the submission finishes processing (status_id > 2) or max_polls is reached.

        :param token: Submission token to poll
        :param max_polls: Maximum polling attempts
        :param poll_interval: Sleep interval in seconds between polls
        :return: ExecutionResult
        """
        last_result = ExecutionResult(
            status="IN_QUEUE",
            is_success=False,
            stdout="",
            stderr="",
            compile_output="",
            execution_time=0.0,
            memory=0,
            status_id=1,
            status_description="In Queue",
            token=token,
        )

        for _ in range(max_polls):
            time.sleep(poll_interval)
            result = self.get_submission(token)
            last_result = result
            # Status IDs 1 (In Queue) and 2 (Processing) mean it's still running
            if result.status_id not in (1, 2):
                return result

        return last_result

    def execute(
        self,
        source_code: str,
        language: str,
        stdin: str = "",
        cpu_time_limit: Optional[float] = None,
        memory_limit: Optional[int] = None,
        wait: bool = True,
        poll_if_queued: bool = True,
        max_polls: int = 20,
        poll_interval: float = 0.5,
    ) -> ExecutionResult:
        """
        Submit code for execution and return structured results.
        Automatically polls if Judge0 returns an In-Queue / Processing status.

        Note: Wrong-answer detection is intentionally not performed here.
        The client executes the code and returns the output; output comparison is
        handled exclusively by the test-case runner.

        :param source_code: Student's source code string
        :param language: Programming language ('python', 'cpp', 'java')
        :param stdin: Standard input to feed into the program
        :param cpu_time_limit: Maximum CPU time in seconds (defaults to self.default_cpu_time_limit)
        :param memory_limit: Maximum memory in kilobytes (defaults to self.default_memory_limit)
        :param wait: If True, requests synchronous execution from Judge0
        :param poll_if_queued: If True, polls until done if Judge0 queues the request
        :param max_polls: Maximum polling iterations
        :param poll_interval: Polling frequency in seconds
        :return: ExecutionResult object
        """
        language_id = self.get_language_id(language)
        time_limit = cpu_time_limit if cpu_time_limit is not None else self.default_cpu_time_limit
        mem_limit = memory_limit if memory_limit is not None else self.default_memory_limit

        payload = {
            "language_id": language_id,
            "source_code": self._b64_encode(source_code),
            "stdin": self._b64_encode(stdin),
            "cpu_time_limit": time_limit,
            "memory_limit": mem_limit,
        }

        wait_str = "true" if wait else "false"
        endpoint = f"{self.base_url}/submissions?base64_encoded=true&wait={wait_str}"
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            return ExecutionResult(
                status="HTTP_ERROR",
                is_success=False,
                stdout="",
                stderr=f"HTTP Error {err.code}: {err.reason}",
                compile_output="",
                execution_time=0.0,
                memory=0,
                status_id=0,
                status_description=f"HTTP {err.code}",
                message=err_body,
            )
        except urllib.error.URLError as err:
            return ExecutionResult(
                status="CONNECTION_ERROR",
                is_success=False,
                stdout="",
                stderr=f"Failed to connect to execution server: {err.reason}",
                compile_output="",
                execution_time=0.0,
                memory=0,
                status_id=0,
                status_description="Connection Error",
                message=str(err),
            )
        except Exception as err:
            return ExecutionResult(
                status="INTERNAL_ERROR",
                is_success=False,
                stdout="",
                stderr=str(err),
                compile_output="",
                execution_time=0.0,
                memory=0,
                status_id=0,
                status_description="Internal Error",
                message=str(err),
            )

        result = self._parse_response(resp_json)

        # If Judge0 returned IN_QUEUE or PROCESSING (or wait=False token) and polling is requested
        if poll_if_queued and result.token and (not wait or result.status_id in (1, 2)):
            result = self.poll_submission(
                result.token,
                max_polls=max_polls,
                poll_interval=poll_interval,
            )

        return result
