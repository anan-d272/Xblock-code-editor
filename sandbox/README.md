# Sandbox Isolation Environment

This directory contains the Docker-based code execution sandbox for the Open edX Coding Exam XBlock.

---

## 1. Architecture & Security Isolation

Untrusted student code must **never** be executed directly on the host machine. The sandbox provides multi-layer isolation:

1. **Network Disconnected (`--network none`):**
   - The container has no network access. Code cannot communicate with the internet, LMS, CMS, MySQL, Redis, or local subnets.

2. **Unprivileged User (`--user 1001:1001`):**
   - Code runs as `sandboxuser` (UID 1001), preventing root privilege escalation.

3. **Strict Resource Constraints:**
   - Memory capped at `--memory 128m` (prevents memory exhaustion attacks).
   - CPU quota limited to `--cpus 0.5` (prevents CPU starvation attacks).

4. **Execution Timeouts:**
   - Hard process-level timeout (`timeout -s SIGKILL`) terminates runaway infinite loops and forks.

5. **Ephemeral Lifecycle (`--rm`):**
   - Containers and temporary files are destroyed immediately upon process exit. Host files are mounted read-only (`:ro`).

---

## 2. Supported Languages

- **Python:** Python 3 (`python3`)
- **C++:** GCC 15 (`g++ -O2 -std=c++17 -Wall`)
- **Java:** OpenJDK 17 (`javac Main.java && java Main`)

---

## 3. Building the Sandbox Image

From the repository root or inside `sandbox/`:

```bash
docker build --network=host -t coding-exam-sandbox:latest sandbox/
```

---

## 4. Testing Execution Manually

```bash
# Run a Python one-liner in the sandbox
docker run --rm --network none -m 128m --cpus 0.5 \
    coding-exam-sandbox:latest python /dev/null /dev/null 5
```

