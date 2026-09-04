FROM ubuntu:22.04

WORKDIR /app

# 1) System packages
RUN apt-get clean && apt-get update && apt-get install -y --no-install-recommends \
    libasound2 \
    libgstreamer1.0-dev \
    libunwind-dev \
    libc++1 \
    libssl-dev \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    jq \
    ca-certificates \
    curl \
    wget \
    libpq-dev \
    libldap2-dev \
    libsasl2-dev \
    cron \
    gcc \
    make \
    libcapture-tiny-perl \
    libdatetime-perl \
    libjson-perl \
    libtimedate-perl \
    && (pip3 install --retries 5 --timeout 30 --upgrade pip setuptools \
        || echo "WARN: pip/setuptools upgrade skipped (PyPI unreachable), continuing with system pip") \
    && curl -sL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# lcov 2.3 from source (Ubuntu 22.04 apt lcov is 1.15, doesn't support --synthesize-missing)
RUN curl -fsSL https://github.com/linux-test-project/lcov/releases/download/v2.3/lcov-2.3.tar.gz -o /tmp/lcov.tar.gz \
    && tar xzf /tmp/lcov.tar.gz -C /tmp \
    && cd /tmp/lcov-2.3 && make install \
    && cd / && rm -rf /tmp/lcov-2.3 /tmp/lcov.tar.gz \
    && lcov --version

# 2) Python deps
# Retries here matter: a single PyPI CDN hiccup used to fail the whole build.
COPY requirements.txt .
RUN pip3 install --retries 5 --timeout 30 -r requirements.txt

# 4) Frontend deps
COPY mercury-frontend/package.json mercury-frontend/package-lock.json mercury-frontend/
RUN cd mercury-frontend && npm install

# 5) Frontend build
COPY mercury-frontend/ mercury-frontend/
RUN cd mercury-frontend && npm run build

# 6) Backend code
COPY . .

CMD ["bash", "deploy/mercury/start_server.sh"]
