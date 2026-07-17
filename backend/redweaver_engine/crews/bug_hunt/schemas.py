"""Pydantic result models for each specialized agent.

Every agent returns a structured result via CrewAI's output_pydantic parameter,
guaranteeing the LLM produces JSON matching this schema.

IMPORTANT: OpenAI structured output requires `additionalProperties: false` on
all object types. This means we CANNOT use `list[dict]` — every nested object
must be a proper Pydantic model. All models use ConfigDict(extra="forbid") to
enforce this constraint.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    """Base model that forbids extra fields (required for OpenAI structured output)."""
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Shared sub-models (used across multiple agent results)
# ---------------------------------------------------------------------------

class FindingItem(_StrictModel):
    """A single security finding. Used by all specialist agents."""

    title: str = Field(description="Short title, e.g. 'Open SSH port 22' or 'Missing X-Frame-Options header'")
    severity: str = Field(default="info", description="One of: critical, high, medium, low, info")
    description: str = Field(default="", description="What the issue is and its potential impact")
    affected_url: str = Field(default="", description="The URL, host, or IP affected")
    evidence: str = Field(default="", description="Raw tool output or proof supporting this finding")
    remediation: str = Field(default="", description="How to fix this issue")
    tool_used: str = Field(default="", description="Tool that discovered this, e.g. 'nmap_scan'")
    cvss_score: float | None = Field(default=None, description="CVSS score 0.0-10.0 if applicable")
    cve_ids: list[str] = Field(default_factory=list, description="CVE identifiers if known")
    cisa_kev: bool = Field(default=False, description="Whether this CVE is in CISA's Known Exploited Vulnerabilities catalog")
    exploitability: str = Field(default="unknown", description="Exploitability: proven, likely, possible, unlikely, unknown")


class ServiceInfo(_StrictModel):
    """A discovered network service."""

    host: str = Field(description="Host IP or hostname")
    port: int = Field(description="Port number")
    protocol: str = Field(default="tcp", description="Protocol: tcp, udp")
    service: str = Field(default="", description="Service name, e.g. 'http', 'ssh'")
    version: str = Field(default="", description="Service version string")
    banner: str = Field(default="", description="Raw banner or fingerprint")


class TechnologyInfo(_StrictModel):
    """A detected technology/software stack."""

    name: str = Field(description="Technology name, e.g. 'Apache', 'WordPress'")
    version: str = Field(default="", description="Version string, e.g. '2.4.49'")
    categories: str = Field(default="", description="Comma-separated categories, e.g. 'web-server,reverse-proxy'")


class PortInfo(_StrictModel):
    """An open port with service details."""

    host: str = Field(description="Host IP or hostname")
    port: int = Field(description="Port number")
    service: str = Field(default="", description="Service name")
    version: str = Field(default="", description="Service version")
    state: str = Field(default="open", description="Port state: open, filtered, closed")


class FormInfo(_StrictModel):
    """An HTML form discovered by crawling."""

    action: str = Field(default="", description="Form action URL")
    method: str = Field(default="GET", description="HTTP method: GET, POST")
    inputs: str = Field(default="", description="Comma-separated input field names")


class InterestingResponse(_StrictModel):
    """A non-404 HTTP response discovered by fuzzing."""

    url: str = Field(description="The URL that returned this response")
    status: int = Field(description="HTTP status code")
    size: int = Field(default=0, description="Response body size in bytes")
    content_type: str = Field(default="", description="Content-Type header value")


class CVEInfo(_StrictModel):
    """A CVE vulnerability reference."""

    cve_id: str = Field(description="CVE identifier, e.g. 'CVE-2024-1234'")
    cvss: float = Field(default=0.0, description="CVSS score 0.0-10.0")
    description: str = Field(default="", description="CVE description")
    affected_versions: str = Field(default="", description="Affected software versions")


class ExploitRef(_StrictModel):
    """A public exploit reference."""

    title: str = Field(description="Exploit title or name")
    url: str = Field(default="", description="URL to exploit code or advisory")
    exploit_type: str = Field(default="", description="Type: PoC, metasploit, manual, etc.")


class BugBountyReport(_StrictModel):
    """A bug bounty report reference."""

    title: str = Field(description="Report title")
    url: str = Field(default="", description="URL to the report")
    severity: str = Field(default="", description="Reported severity")


class DefaultCredential(_StrictModel):
    """A default credential for a service."""

    service: str = Field(description="Service name")
    username: str = Field(default="", description="Default username")
    password: str = Field(default="", description="Default password")


class AttackChain(_StrictModel):
    """A multi-step attack path identified through correlation."""

    name: str = Field(description="Attack chain name, e.g. 'Admin Panel + Default Creds + RCE'")
    steps: list[str] = Field(default_factory=list, description="Ordered steps in the attack chain")
    severity: str = Field(default="high", description="Overall severity of the chain")
    findings_involved: list[str] = Field(default_factory=list, description="Finding titles involved")
    likelihood: str = Field(default="possible", description="Likelihood: confirmed, likely, possible, unlikely")


class PrioritizedFinding(_StrictModel):
    """A finding with exploitability and impact assessment."""

    title: str = Field(description="Finding title")
    severity: str = Field(default="info", description="Severity level")
    exploitability: str = Field(default="unknown", description="How exploitable: proven, likely, possible")
    impact: str = Field(default="", description="Business impact description")
    priority_rank: int = Field(default=0, description="Priority ranking (1 = highest)")


class EscalationPath(_StrictModel):
    """A privilege escalation path."""

    method: str = Field(description="Escalation method, e.g. 'SUID binary', 'kernel exploit'")
    binary: str = Field(default="", description="Binary or service involved")
    details: str = Field(default="", description="How to exploit this path")


class CredentialInfo(_StrictModel):
    """A discovered credential."""

    source: str = Field(description="Where the credential was found, e.g. '/etc/shadow', 'env var'")
    username: str = Field(default="", description="Username or account name")
    credential_type: str = Field(default="", description="Type: password, hash, key, token")


class TunnelInfo(_StrictModel):
    """An established SSH tunnel."""

    tunnel_type: str = Field(description="Tunnel type: local, remote, dynamic, sshuttle")
    local_port: int = Field(default=0, description="Local port number")
    remote_host: str = Field(default="", description="Remote host targeted")
    remote_port: int = Field(default=0, description="Remote port targeted")


class FlagInfo(_StrictModel):
    """A captured flag or proof."""

    flag_type: str = Field(description="Flag type: local, root, proof, user")
    path: str = Field(default="", description="File path where flag was found")
    content: str = Field(default="", description="Flag content")
    host: str = Field(default="", description="Host where flag was found")


class EvidenceFile(_StrictModel):
    """An evidence file collected during post-exploitation."""

    local_path: str = Field(default="", description="Local path where file was saved")
    remote_path: str = Field(default="", description="Original remote path")
    description: str = Field(default="", description="What this evidence shows")


# ---------------------------------------------------------------------------
# Agent result models
# ---------------------------------------------------------------------------

class ReconResult(_StrictModel):
    """Structured output from the Reconnaissance agent."""

    subdomains: list[str] = Field(default_factory=list, description="Discovered subdomains")
    alive_hosts: list[str] = Field(default_factory=list, description="Hosts confirmed alive via httpx")
    technologies: list[TechnologyInfo] = Field(default_factory=list, description="Technology stacks detected")
    open_ports: list[PortInfo] = Field(default_factory=list, description="Open ports and services")
    services: list[ServiceInfo] = Field(default_factory=list, description="Discovered services with versions")
    emails: list[str] = Field(default_factory=list, description="Email addresses found via OSINT")
    hostnames: list[str] = Field(default_factory=list, description="Hostnames found via OSINT")
    findings: list[FindingItem] = Field(default_factory=list, description="Security findings from recon")
    summary: str = Field(default="", description="Human-readable summary of reconnaissance results")


class CrawlerResult(_StrictModel):
    """Structured output from the Web Crawler agent."""

    endpoints: list[str] = Field(default_factory=list, description="Discovered web endpoints")
    js_files: list[str] = Field(default_factory=list, description="JavaScript files found")
    forms: list[FormInfo] = Field(default_factory=list, description="HTML forms discovered")
    api_routes: list[str] = Field(default_factory=list, description="API routes found")
    admin_panels: list[str] = Field(default_factory=list, description="Admin/dashboard endpoints found")
    config_files: list[str] = Field(default_factory=list, description="Config/backup files discovered")
    findings: list[FindingItem] = Field(default_factory=list, description="Security findings from crawling")
    summary: str = Field(default="", description="Summary of web crawling results")


class VulnScanResult(_StrictModel):
    """Structured output from the Vulnerability Scanner agent."""

    findings: list[FindingItem] = Field(default_factory=list, description="Security findings from scanning")
    templates_matched: int = Field(default=0, description="Number of nuclei templates matched")
    cves_found: list[str] = Field(default_factory=list, description="CVE IDs discovered")
    kev_matches: list[str] = Field(default_factory=list, description="CVEs in CISA KEV catalog")
    summary: str = Field(default="", description="Summary of vulnerability scanning results")


class FuzzerResult(_StrictModel):
    """Structured output from the Fuzzer agent."""

    discovered_paths: list[str] = Field(default_factory=list, description="Hidden paths discovered")
    interesting_responses: list[InterestingResponse] = Field(default_factory=list, description="Non-404 responses")
    findings: list[FindingItem] = Field(default_factory=list, description="Security findings from fuzzing")
    summary: str = Field(default="", description="Summary of fuzzing results")


class WebSearchResult(_StrictModel):
    """Structured output from the Web Search agent."""

    cves: list[CVEInfo] = Field(default_factory=list, description="CVEs found for target technologies")
    exploits: list[ExploitRef] = Field(default_factory=list, description="Public exploit references")
    advisories: list[str] = Field(default_factory=list, description="Security advisories found")
    bug_bounty_reports: list[BugBountyReport] = Field(default_factory=list, description="Bug bounty reports")
    default_credentials: list[DefaultCredential] = Field(default_factory=list, description="Default credentials")
    findings: list[FindingItem] = Field(default_factory=list, description="Security findings from web research")
    summary: str = Field(default="", description="Summary of security intelligence gathered")


class ExploitAnalysisResult(_StrictModel):
    """Structured output from the Exploit Analyst agent."""

    attack_chains: list[AttackChain] = Field(default_factory=list, description="Identified attack chains")
    prioritized_findings: list[PrioritizedFinding] = Field(default_factory=list, description="Findings sorted by impact")
    false_positives: list[str] = Field(default_factory=list, description="Finding titles identified as false positives")
    risk_assessment: str = Field(default="", description="Overall risk assessment narrative")
    risk_rating: str = Field(default="medium", description="Overall risk: critical, high, medium, low, informational")
    findings: list[FindingItem] = Field(default_factory=list, description="Analyzed and enriched findings")
    summary: str = Field(default="", description="Summary of exploit analysis")


class HuntReport(_StrictModel):
    """Structured output from the Report Writer agent.

    Professional penetration testing report output.
    """

    executive_summary: str = Field(
        default="",
        description="Short executive blurb only (2–4 sentences). The full report must be in report_markdown.",
    )
    scope_and_methodology: str = Field(default="", description="Scope constraints and methodology used")
    findings: list[FindingItem] = Field(default_factory=list, description="All findings compiled from all agents")
    total_by_severity: str = Field(default="", description="Finding counts by severity as text, e.g. 'Critical: 2, High: 5, Medium: 3'")
    risk_rating: str = Field(default="medium", description="Overall risk: critical, high, medium, low, informational")
    report_markdown: str = Field(
        default="",
        description=(
            "Complete client-facing report in Markdown only. Must include: H1 title; ## sections (Executive Summary, "
            "Target Overview, Methodology, Attack Surface, Detailed Findings, Attack Chains, Remediation Roadmap, "
            "Tools & Techniques, Appendices); markdown tables where data is tabular; bullet/numbered lists; "
            "fenced code blocks for evidence; blockquotes for notes (e.g. > **Note:**). No unstructured plain-text dump."
        ),
    )
    recommendations: list[str] = Field(default_factory=list, description="Ordered remediation priorities")
    tools_used: list[str] = Field(default_factory=list, description="Tools used during the assessment")
    agents_executed: list[str] = Field(default_factory=list, description="Agent names that contributed findings")
    attack_chains: list[AttackChain] = Field(default_factory=list, description="Attack chains from exploit analyst")


class PTReportResult(_StrictModel):
    """Structured output from the PT Reporter agent."""

    findings: list[FindingItem] = Field(default_factory=list, description="Security findings identified")
    attack_chains: list[AttackChain] = Field(default_factory=list, description="Attack chain analysis")
    report_markdown: str = Field(default="", description="Full report in Markdown format")
    summary: str = Field(default="", description="Summary of PT Reporter analysis")


class PrivEscResult(_StrictModel):
    """Structured output from the Privilege Escalation agent."""

    current_user: str = Field(default="", description="Current user context on target")
    escalated_to: str = Field(default="", description="User escalated to, e.g. 'root'")
    escalation_paths: list[EscalationPath] = Field(default_factory=list, description="Discovered privesc paths")
    suid_binaries: list[str] = Field(default_factory=list, description="SUID binaries found")
    capabilities: list[str] = Field(default_factory=list, description="Binaries with capabilities")
    sudo_permissions: list[str] = Field(default_factory=list, description="Sudo permissions available")
    writable_files: list[str] = Field(default_factory=list, description="Security-critical writable files")
    cron_jobs: list[str] = Field(default_factory=list, description="Exploitable cron jobs")
    kernel_info: str = Field(default="", description="Kernel version and potential exploits")
    credentials_found: list[CredentialInfo] = Field(default_factory=list, description="Discovered credentials")
    findings: list[FindingItem] = Field(default_factory=list, description="Security findings from privilege escalation")
    summary: str = Field(default="", description="Summary of privilege escalation assessment")


class TunnelPivotResult(_StrictModel):
    """Structured output from the Tunnel & Pivot agent."""

    tunnels_established: list[TunnelInfo] = Field(default_factory=list, description="Active tunnels established")
    internal_hosts_discovered: list[str] = Field(default_factory=list, description="Internal hosts found via pivoting")
    network_segments: list[str] = Field(default_factory=list, description="Network segments reached (CIDR)")
    pivot_chain: list[str] = Field(default_factory=list, description="Chain of pivots performed")
    findings: list[FindingItem] = Field(default_factory=list, description="Security findings from pivoting")
    summary: str = Field(default="", description="Summary of tunneling and pivoting results")


class PostExploitResult(_StrictModel):
    """Structured output from the Post-Exploitation agent."""

    flags_found: list[FlagInfo] = Field(default_factory=list, description="Flags/proofs captured")
    credentials_harvested: list[CredentialInfo] = Field(default_factory=list, description="Credentials found")
    sensitive_files: list[str] = Field(default_factory=list, description="Sensitive files discovered with paths")
    persistence_mechanisms: list[str] = Field(default_factory=list, description="Persistence methods established")
    evidence_collected: list[EvidenceFile] = Field(default_factory=list, description="Evidence files collected")
    findings: list[FindingItem] = Field(default_factory=list, description="Security findings from post-exploitation")
    summary: str = Field(default="", description="Summary of post-exploitation results")
