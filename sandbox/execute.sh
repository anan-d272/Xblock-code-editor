#!/bin/bash
set -eo pipefail

LANGUAGE="$1"
SOURCE_FILE="$2"
INPUT_FILE="$3"
TIMEOUT_SEC="${4:-5}"
MAX_OUTPUT_BYTES="${5:-1048576}"

WORKDIR="/sandbox_run"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

case "$LANGUAGE" in
    python|py|python3)
        cp "$SOURCE_FILE" solution.py
        if [ -f "$INPUT_FILE" ]; then
            timeout -s SIGKILL "${TIMEOUT_SEC}s" python3 -u solution.py < "$INPUT_FILE" | head -c "$MAX_OUTPUT_BYTES"
        else
            timeout -s SIGKILL "${TIMEOUT_SEC}s" python3 -u solution.py | head -c "$MAX_OUTPUT_BYTES"
        fi
        ;;

    cpp|c++)
        cp "$SOURCE_FILE" solution.cpp
        # Compile stage
        if ! g++ -O2 -std=c++17 -Wall solution.cpp -o solution 2> compile.err; then
            cat compile.err >&2
            exit 101
        fi
        # Execute stage
        if [ -f "$INPUT_FILE" ]; then
            timeout -s SIGKILL "${TIMEOUT_SEC}s" ./solution < "$INPUT_FILE" | head -c "$MAX_OUTPUT_BYTES"
        else
            timeout -s SIGKILL "${TIMEOUT_SEC}s" ./solution | head -c "$MAX_OUTPUT_BYTES"
        fi
        ;;

    java)
        cp "$SOURCE_FILE" Main.java
        # Compile stage
        if ! javac Main.java 2> compile.err; then
            cat compile.err >&2
            exit 101
        fi
        # Execute stage
        if [ -f "$INPUT_FILE" ]; then
            timeout -s SIGKILL "${TIMEOUT_SEC}s" java -Xmx128m Main < "$INPUT_FILE" | head -c "$MAX_OUTPUT_BYTES"
        else
            timeout -s SIGKILL "${TIMEOUT_SEC}s" java -Xmx128m Main | head -c "$MAX_OUTPUT_BYTES"
        fi
        ;;

    *)
        echo "Error: Unsupported language '$LANGUAGE'" >&2
        exit 102
        ;;
esac

