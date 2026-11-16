"""
Docker Sandbox Execution Client.
Executes student code inside a hardened, isolated local Docker container.
Used as an offline/air-gapped fallback or standalone execution engine.
"""
import os
import shutil
import subprocess
import tempfile
import time
from typing import Optional
from .client import ExecutionResult


class DockerSandboxClient:
    """Executes code inside an isolated Docker container with resource quotas."""

    IMAGE_NAME = os.environ.get("SANDBOX_DOCKER_IMAGE", "coding-exam-sandbox:latest")

    def __init__(
        self,
        image_name: Optional[str] = None,
        cpu_limit: str = "0.5",
        memory_limit: str = "128m",
        default_timeout: int = 10,
        max_output_bytes: int = 1048576,
    ):
        self.image_name = image_name or self.IMAGE_NAME
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.default_timeout = default_timeout
        self.max_output_bytes = max_output_bytes

    def execute(
        self,
        source_code: str,
        language: str,
        stdin: str = "",
        cpu_time_limit: Optional[float] = None,
        memory_limit: Optional[int] = None,
        **kwargs,
    ) -> ExecutionResult:
        """
        Execute code inside the local Docker sandbox container.

        :param source_code: Student source code
        :param language: 'python', 'cpp', 'c++', 'java'
        :param stdin: Input string
        :param cpu_time_limit: Timeout in seconds (defaults to self.default_timeout)
        :param memory_limit: Memory limit in KB (defaults to 128000 KB)
        :return: ExecutionResult matching Judge0 output format
        """
        norm_lang = language.strip().lower()
        ext_map = {
            "python": "solution.py",
            "python3": "solution.py",
            "py": "solution.py",
            "cpp": "solution.cpp",
            "c++": "solution.cpp",
            "java": "Main.java",
        }

        if norm_lang not in ext_map:
            return ExecutionResult(
                status="ERROR",
                is_success=False,
                stdout="",
                stderr=f"Unsupported language: {language}",
                compile_output="",
                execution_time=0.0,
                memory=0,
                status_id=0,
                status_description="Unsupported Language",
                message=f"Language '{language}' not supported by Docker sandbox",
            )

        src_filename = ext_map[norm_lang]
        tmp_dir = tempfile.mkdtemp(prefix="xblock_sandbox_")

        try:
            src_path = os.path.join(tmp_dir, src_filename)
            in_path = os.path.join(tmp_dir, "input.in")

            with open(src_path, "w", encoding="utf-8") as f:
                f.write(source_code)
            with open(in_path, "w", encoding="utf-8") as f:
                f.write(stdin)

            # Ensure non-root container user (UID 1001) can read files
            os.chmod(tmp_dir, 0o777)
            os.chmod(src_path, 0o666)
            os.chmod(in_path, 0o666)

            mem_kb = int(memory_limit) if memory_limit is not None else 128000
            mem_flag = f"{max(32, mem_kb // 1024)}m"

            actual_time = float(cpu_time_limit) if cpu_time_limit is not None else float(self.default_timeout)
            timeout_sec = int(max(1, actual_time))

            cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "-m", mem_flag,
                "--cpus", self.cpu_limit,
                "--user", "1001:1001",
                "-v", f"{tmp_dir}:/sandbox:ro",
                self.image_name,
                norm_lang,
                f"/sandbox/{src_filename}",
                "/sandbox/input.in",
                str(timeout_sec),
                str(self.max_output_bytes),
            ]

            start_t = time.time()
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec + 5,
            )
            elapsed = round(time.time() - start_t, 3)

            # Exit code 101 denotes compilation error in execute.sh
            if proc.returncode == 101:
                return ExecutionResult(
                    status="COMPILATION_ERROR",
                    is_success=False,
                    stdout="",
                    stderr=proc.stderr,
                    compile_output=proc.stderr,
                    execution_time=elapsed,
                    memory=0,
                    status_id=6,
                    status_description="Compilation Error",
                )

            # Exit code 141 indicates SIGPIPE (output exceeded maximum allowed bytes)
            if proc.returncode == 141:
                return ExecutionResult(
                    status="OUTPUT_LIMIT_EXCEEDED",
                    is_success=False,
                    stdout=proc.stdout[:self.max_output_bytes],
                    stderr="Program exceeded maximum output size limit.",
                    compile_output="",
                    execution_time=elapsed,
                    memory=0,
                    status_id=14,
                    status_description="Output Limit Exceeded",
                )

            # Exit code 137 indicates SIGKILL / Out of Memory / Timeout
            if proc.returncode in (137, 124):
                return ExecutionResult(
                    status="TIME_LIMIT_EXCEEDED",
                    is_success=False,
                    stdout=proc.stdout,
                    stderr="Execution timed out.",
                    compile_output="",
                    execution_time=elapsed,
                    memory=0,
                    status_id=5,
                    status_description="Time Limit Exceeded",
                )

            if proc.returncode != 0:
                return ExecutionResult(
                    status="RUNTIME_ERROR",
                    is_success=False,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    compile_output="",
                    execution_time=elapsed,
                    memory=0,
                    status_id=11,
                    status_description=f"Runtime Error (Exit Code {proc.returncode})",
                )

            return ExecutionResult(
                status="ACCEPTED",
                is_success=True,
                stdout=proc.stdout,
                stderr=proc.stderr,
                compile_output="",
                execution_time=elapsed,
                memory=0,
                status_id=3,
                status_description="Accepted",
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                status="TIME_LIMIT_EXCEEDED",
                is_success=False,
                stdout="",
                stderr="Container execution timed out on host.",
                compile_output="",
                execution_time=float(cpu_time_limit or self.default_timeout),
                memory=0,
                status_id=5,
                status_description="Time Limit Exceeded",
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
                status_id=13,
                status_description="Internal Error",
                message=str(err),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
