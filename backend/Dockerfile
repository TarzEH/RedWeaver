# RedWeaver backend - multi-agent bug hunting with security tools
# Stages: tools (OS + CLI scanners) -> deps (pip) -> runtime (app code only)

FROM python:3.11-slim AS tools

# Install system packages: nmap, build deps for Go tools (gcc for CGO)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    git \
    wget \
    curl \
    unzip \
    ca-certificates \
    perl \
    libnet-ssleay-perl \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install nikto from source (not in Debian trixie repos)
RUN git clone --depth 1 https://github.com/sullo/nikto.git /opt/nikto \
    && ln -s /opt/nikto/program/nikto.pl /usr/local/bin/nikto \
    && chmod +x /opt/nikto/program/nikto.pl

# Install whatweb from source
RUN git clone --depth 1 https://github.com/urbanadventurer/WhatWeb.git /opt/whatweb \
    && ln -s /opt/whatweb/whatweb /usr/local/bin/whatweb \
    && chmod +x /opt/whatweb/whatweb

# Install Go for building security tools
ENV GOVERSION=1.24.1
RUN wget -q "https://go.dev/dl/go${GOVERSION}.linux-$(dpkg --print-architecture).tar.gz" -O /tmp/go.tar.gz \
    && tar -C /usr/local -xzf /tmp/go.tar.gz \
    && rm /tmp/go.tar.gz
ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"

# Install Go-based security tools
RUN go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest \
    && go install github.com/projectdiscovery/httpx/cmd/httpx@latest \
    && go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest \
    && go install github.com/projectdiscovery/katana/cmd/katana@latest \
    && go install github.com/ffuf/ffuf/v2@latest \
    && go install github.com/OJ/gobuster/v3@latest

# Update nuclei templates
RUN nuclei -update-templates 2>/dev/null || true

# Install theHarvester via pip
RUN pip install --no-cache-dir theHarvester 2>/dev/null || true

# Create wordlists directory
RUN mkdir -p /usr/share/wordlists/dirb \
    && wget -q "https://raw.githubusercontent.com/v0re/dirb/master/wordlists/common.txt" \
       -O /usr/share/wordlists/dirb/common.txt 2>/dev/null || true

# Python dependencies (cached when only app/ changes)
FROM tools AS deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
FROM deps AS runtime
COPY app/ ./app/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
