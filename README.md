# Coding Exam XBlock

An Open edX XBlock for coding exams (Java / Python / C++).

> **Status:** early "Hello" slice — only the scaffold is present.

---

## Repository layout

```
Xblock-code-editor/
├── coding_exam/
│   ├── __init__.py      # re-exports CodingExamXBlock
│   ├── block.py         # XBlock definition
│   ├── runner/          # (teammate owns this — do not edit)
│   └── static/          # CSS / JS assets (future)
├── sandbox/             # (teammate owns this — do not edit)
├── setup.py
└── README.md
```

---

## Installing into Tutor (development)

These steps assume Tutor 19 (Ulmo) running via `tutor local`.

### 1 — Mount the repo into the LMS and CMS containers

```bash
# Replace the path with where you cloned the repo inside WSL
tutor mounts add /path/to/Xblock-code-editor
```

This tells Tutor to bind-mount the repo into the containers **and** run
`pip install -e .` automatically on the next start, so the entry point
`coding_exam` becomes importable.

### 2 — Restart Tutor so the mount takes effect

```bash
tutor local restart
```

### 3 — Enable the XBlock in Open edX

1. Open **Studio** → your course → **Settings → Advanced Settings**.
2. Find **Advanced Module List**.
3. Add `"coding_exam"` to the JSON array, e.g.:
   ```json
   ["coding_exam"]
   ```
4. Click **Save Changes**.

### 4 — Add the block to a unit

1. In a unit, click **Advanced** (the green button).
2. Select **Coding Exam**.
3. The student view shows: *Hello from the Coding Exam XBlock*.

---

## Local development (without Tutor)

```bash
# Create a virtualenv and install in editable mode
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
```

Verify the entry point is registered:

```bash
python -c "import pkg_resources; print(list(pkg_resources.iter_entry_points('xblock.v1')))"
# Should print something containing 'coding_exam'
```

