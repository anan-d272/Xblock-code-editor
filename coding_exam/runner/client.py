"""
Execution client for dispatching student code to the Judge0 REST API.
Handles base64 encoding/decoding, language mapping, resource limits, and error handling.
"""
import base64
import json
import os
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
        }


class Judge0Client:
    """Client for executing code against a Judge0 CE API instance."""

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
    ):
        """
        Initialize the Judge0 client.

        :param base_url: Judge0 API base URL (defaults to JUDGE0_URL env var or public CE)
        :param user_agent: User-Agent header (required to prevent WAF blocks)
        :param timeout: HTTP request timeout in seconds
        """
        self.base_url = (base_url or os.environ.get("JUDGE0_URL", "https://ce.judge0.com")).rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout

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

    def execute(
        self,
        source_code: str,
        language: str,
        stdin: str = "",
        cpu_time_limit: float = 5.0,
        memory_limit: int = 128000,
    ) -> ExecutionResult:
        """
        Submit code for synchronous execution and return structured results.

        :param source_code: Student's source code string
        :param language: Programming language ('python', 'cpp', 'java')
        :param stdin: Standard input to feed into the program
        :param cpu_time_limit: Maximum CPU time in seconds
        :param memory_limit: Maximum memory in kilobytes
        :return: ExecutionResult object
        """
        language_id = self.get_language_id(language)

        payload = {
            "language_id": language_id,
            "source_code": self._b64_encode(source_code),
            "stdin": self._b64_encode(stdin),
            "cpu_time_limit": cpu_time_limit,
            "memory_limit": memory_limit,
        }

        endpoint = f"{self.base_url}/submissions?base64_encoded=true&wait=true"
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

        # Parse and decode response attributes
        status_info = resp_json.get("status", {})
        status_id = status_info.get("id", 0)
        status_desc = status_info.get("description", "Unknown")

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
        )

