"""SSRF / scan-scope guard for tool targets.

RedWeaver is a pentest tool, so scanning private networks is legitimate and is
NOT blocked by default. What is *never* legitimate is hitting cloud metadata
endpoints or link-local addresses (the classic SSRF→credential-exfil pivot),
so those are always blocked. Loopback is blocked by default (scanning the
worker container itself), and RFC1918/ULA private ranges can be blocked in
locked-down (e.g. SaaS) deployments via an env flag.

Env flags:
  RW_BLOCK_PRIVATE_TARGETS=1  -> also block RFC1918/ULA private ranges
  RW_ALLOW_LOOPBACK=1         -> permit loopback targets
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

# Cloud metadata services (AWS/GCP/Azure/Alibaba all share 169.254.169.254).
_METADATA_IPS = {"169.254.169.254", "fd00:ec2::254"}


def _host_from(target: str) -> str:
    t = (target or "").strip()
    if not t:
        return ""
    if "://" in t:
        return (urlparse(t).hostname or "").strip()
    t = t.split("/", 1)[0]          # drop path / CIDR suffix
    if t.startswith("["):           # [ipv6]:port
        return t[1:].split("]", 1)[0]
    if t.count(":") == 1:           # host:port
        t = t.split(":", 1)[0]
    return t.strip()


def _resolved_ips(host: str) -> list[str]:
    try:
        ipaddress.ip_address(host)
        return [host]               # already a literal IP
    except ValueError:
        pass
    try:
        return list({info[4][0] for info in socket.getaddrinfo(host, None)})
    except Exception:
        return []                   # DNS failure -> fail open (the tool will just fail)


def check_target(target: str) -> tuple[bool, str]:
    """Return (allowed, reason). Only blocks targets that *resolve* to a
    disallowed address, so non-network inputs (search queries, CVE ids) pass."""
    host = _host_from(target)
    if not host:
        return True, ""
    block_private = os.environ.get("RW_BLOCK_PRIVATE_TARGETS", "0") == "1"
    allow_loopback = os.environ.get("RW_ALLOW_LOOPBACK", "0") == "1"
    for ipstr in _resolved_ips(host):
        if ipstr in _METADATA_IPS:
            return False, f"cloud metadata endpoint ({ipstr})"
        try:
            ip = ipaddress.ip_address(ipstr)
        except ValueError:
            continue
        if ip.is_link_local:
            return False, f"link-local/metadata address ({ipstr})"
        if ip.is_loopback and not allow_loopback:
            return False, f"loopback address ({ipstr})"
        if ip.is_private and not ip.is_loopback and not ip.is_link_local and block_private:
            return False, f"private address ({ipstr}) blocked by RW_BLOCK_PRIVATE_TARGETS"
    return True, ""
