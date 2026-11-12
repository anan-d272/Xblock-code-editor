# Lightweight, isolated multi-language sandbox environment for Open edX Coding Exam XBlock
FROM alpine:latest

# Install compilers and runtimes for Python, C++, and Java
RUN apk update && apk add --no-cache \
    python3 \
    g++ \
    openjdk17-jdk \
    coreutils \
    bash \
    && rm -rf /var/cache/apk/*

# Create a low-privilege unprivileged user to execute untrusted code
RUN adduser -D -u 1001 -s /bin/sh sandboxuser

# Prepare directories
RUN mkdir -p /sandbox /sandbox_run && \
    chown -R sandboxuser:sandboxuser /sandbox /sandbox_run

# Copy execution entrypoint script
COPY execute.sh /usr/local/bin/execute.sh
RUN chmod +x /usr/local/bin/execute.sh

USER sandboxuser
WORKDIR /sandbox_run

ENTRYPOINT ["/usr/local/bin/execute.sh"]

