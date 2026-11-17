"""
Tutor plugin definition for Coding Exam XBlock and Execution Service.
Compatible with Tutor 19 (v1 API).
"""
from __future__ import annotations

import click
from tutor import fmt, hooks

# 1. Configuration defaults
hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("CODING_EXAM_DOCKER_IMAGE", "coding-exam-sandbox:latest"),
        ("CODING_EXAM_EXECUTION_TIMEOUT", 10),
        ("CODING_EXAM_MEMORY_LIMIT", "128m"),
        ("CODING_EXAM_CPU_LIMIT", "0.5"),
        ("CODING_EXAM_JUDGE0_URL", "https://ce.judge0.com"),
        ("CODING_EXAM_EXECUTION_ENGINE", "judge0"),
    ]
)

# 2. Environment patches for Open edX common settings
COMMON_SETTINGS_PATCH = """
# Coding Exam XBlock Configuration
CODING_EXAM_SETTINGS = {
    "EXECUTION_ENGINE": "{{ CODING_EXAM_EXECUTION_ENGINE }}",
    "JUDGE0_URL": "{{ CODING_EXAM_JUDGE0_URL }}",
    "EXECUTION_TIMEOUT": {{ CODING_EXAM_EXECUTION_TIMEOUT }},
    "SANDBOX_IMAGE": "{{ CODING_EXAM_DOCKER_IMAGE }}",
    "MEMORY_LIMIT": "{{ CODING_EXAM_MEMORY_LIMIT }}",
    "CPU_LIMIT": "{{ CODING_EXAM_CPU_LIMIT }}",
}
"""

hooks.Filters.ENV_PATCHES.add_items(
    [
        ("openedx-common-settings", COMMON_SETTINGS_PATCH),
        (
            "lms-env",
            "CODING_EXAM_JUDGE0_URL: {{ CODING_EXAM_JUDGE0_URL }}\n"
            "CODING_EXAM_EXECUTION_ENGINE: {{ CODING_EXAM_EXECUTION_ENGINE }}\n",
        ),
        (
            "cms-env",
            "CODING_EXAM_JUDGE0_URL: {{ CODING_EXAM_JUDGE0_URL }}\n"
            "CODING_EXAM_EXECUTION_ENGINE: {{ CODING_EXAM_EXECUTION_ENGINE }}\n",
        ),
    ]
)

# 3. Automatic compose mounts for the XBlock repository
@hooks.Filters.COMPOSE_MOUNTS.add()
def _add_coding_exam_mounts(
    mounts: list[tuple[str, str]], name: str
) -> list[tuple[str, str]]:
    if name in ("Xblock-code-editor", "xblock-code-editor"):
        mounts.append(("lms", "/openedx/Xblock-code-editor"))
        mounts.append(("cms", "/openedx/Xblock-code-editor"))
    return mounts


# 4. Custom Tutor CLI command
@click.group(name="coding-exam")
def coding_exam_group() -> None:
    """Manage Coding Exam XBlock configuration and execution status."""
    pass


@coding_exam_group.command(name="status")
def coding_exam_status() -> None:
    """Check Coding Exam execution service status."""
    fmt.echo_info("Coding Exam XBlock Plugin is installed and active.")


hooks.Filters.CLI_COMMANDS.add_item(coding_exam_group)
