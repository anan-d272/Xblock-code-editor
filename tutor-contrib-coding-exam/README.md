# Tutor Plugin: Coding Exam XBlock (`tutor-contrib-coding-exam`)

This Tutor plugin packages, configures, and manages the **Coding Exam XBlock** and its backend execution infrastructure for Open edX.

---

## Features

- **Automatic XBlock Installation:** Registers bind-mounts and pip requirements so the Coding Exam XBlock is available in both LMS and Studio (CMS).
- **Execution Service Configuration:** Sets up connection parameters for the code execution runner (Judge0 API and local Docker sandbox).
- **Customizable Quotas:** Configurable CPU time limits, memory limits, and container sandbox images via standard Tutor settings.
- **Tutor CLI Integration:** Provides `tutor coding-exam status` and `tutor coding-exam check` commands.

---

## Installation

Inside the Tutor environment:

```bash
pip install -e /path/to/Xblock-code-editor/tutor-contrib-coding-exam
tutor plugins enable coding_exam
```

Save configuration and apply changes:

```bash
tutor config save
tutor local restart
```

---

## Configuration Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `CODING_EXAM_EXECUTION_ENGINE` | `"judge0"` | Execution backend (`"judge0"` or `"docker"`) |
| `CODING_EXAM_JUDGE0_URL` | `"https://ce.judge0.com"` | Endpoint URL for Judge0 CE API |
| `CODING_EXAM_EXECUTION_TIMEOUT` | `10` | Hard timeout in seconds for code execution |
| `CODING_EXAM_MEMORY_LIMIT` | `"128m"` | Memory limit for container execution |
| `CODING_EXAM_CPU_LIMIT` | `"0.5"` | CPU quota for execution container |
| `CODING_EXAM_DOCKER_IMAGE` | `"coding-exam-sandbox:latest"` | Image name for local Docker sandbox |

To override any setting:

```bash
tutor config save --set CODING_EXAM_EXECUTION_TIMEOUT=15
```
