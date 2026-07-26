"""Unit tests for asset-inventory aggregation.

The bug these pin: the endpoint used to return only ``max_severity`` and a
total, and the frontend "recovered" the split by assuming one finding at the
peak and *every other one at low*. On a session with 12 critical / 18 high /
15 medium / 2 low that rendered as "Critical 5, Low 42" in the page header —
directly contradicting the severity chart underneath it. The histogram has to
come from the data, so these tests assert it does.
"""
from dataclasses import dataclass, field

from apps.hunts.assets import SEVERITY_RANK, aggregate_assets, host_of


@dataclass
class F:
    """Stand-in for a Finding — only the fields the aggregator reads."""

    severity: str = "info"
    title: str = ""
    cve_ids: list = field(default_factory=list)
    cisa_kev: bool = False
    exploitability: str = ""


def rows(host, *findings):
    return [(host, f) for f in findings]


# ── the histogram ──────────────────────────────────────────────────────────
def test_by_severity_counts_every_finding_not_just_the_peak():
    out = aggregate_assets(
        rows("a.example", F("critical"), F("high"), F("high"), F("medium"), F("low"))
    )
    assert out[0]["by_severity"] == {
        "critical": 1,
        "high": 2,
        "medium": 1,
        "low": 1,
        "info": 0,
    }


def test_histogram_sums_to_the_reported_finding_count():
    out = aggregate_assets(
        rows("a.example", F("critical"), F("high"), F("medium"), F("medium"), F("info"))
    )
    asset = out[0]
    assert sum(asset["by_severity"].values()) == asset["findings"] == 5


def test_non_peak_findings_are_not_relabelled_low():
    """The exact shape of the old guess: 1 critical + 4 high must not become
    1 critical + 4 low."""
    out = aggregate_assets(rows("a.example", F("critical"), *[F("high")] * 4))
    assert out[0]["by_severity"]["low"] == 0
    assert out[0]["by_severity"]["high"] == 4


def test_every_severity_key_is_present_even_at_zero():
    out = aggregate_assets(rows("a.example", F("high")))
    assert set(out[0]["by_severity"]) == set(SEVERITY_RANK)


def test_unknown_severity_is_bucketed_as_info_not_dropped():
    out = aggregate_assets(rows("a.example", F("bogus"), F(""), F("high")))
    asset = out[0]
    assert asset["by_severity"]["info"] == 2
    assert sum(asset["by_severity"].values()) == asset["findings"] == 3


# ── max severity ───────────────────────────────────────────────────────────
def test_max_severity_is_the_worst_seen_regardless_of_order():
    assert aggregate_assets(rows("a", F("low"), F("critical"), F("medium")))[0][
        "max_severity"
    ] == "critical"
    assert aggregate_assets(rows("a", F("critical"), F("low")))[0][
        "max_severity"
    ] == "critical"


def test_max_severity_defaults_to_info_for_info_only_hosts():
    assert aggregate_assets(rows("a", F("info"), F("info")))[0]["max_severity"] == "info"


# ── grouping and ordering ──────────────────────────────────────────────────
def test_findings_group_by_host():
    out = aggregate_assets(
        rows("a.example", F("high"), F("low")) + rows("b.example", F("critical"))
    )
    by_host = {a["host"]: a for a in out}
    assert by_host["a.example"]["findings"] == 2
    assert by_host["b.example"]["findings"] == 1


def test_hosts_sort_by_severity_then_finding_count():
    out = aggregate_assets(
        rows("low1", F("low"))
        + rows("crit-few", F("critical"))
        + rows("crit-many", F("critical"), F("info"), F("info"))
    )
    assert [a["host"] for a in out] == ["crit-many", "crit-few", "low1"]


# ── the incidental extraction: ports, tech, cves, exploitability ───────────
def test_open_port_is_parsed_out_of_the_title():
    out = aggregate_assets(
        rows("a", F("info", "Open TCP port 8080 (http-alt)"), F("info", "Open TCP port 443 (https)"))
    )
    assert out[0]["ports"] == [443, 8080]


def test_detected_technology_is_parsed_out_of_the_title():
    out = aggregate_assets(
        rows("a", F("info", "Technology detected: nginx 1.18.0"), F("info", "WAF detected: Cloudflare"))
    )
    assert out[0]["technologies"] == ["cloudflare", "nginx 1.18.0"]


def test_a_negative_finding_does_not_become_a_technology():
    """"No open ports detected on <host>" used to yield a technology literally
    named "on <host>" — the Technologies column filled with hostnames."""
    out = aggregate_assets(
        rows(
            "a",
            F("info", "No open ports detected on shop.acme.example"),
            F("info", "No vulnerabilities detected during the scan"),
        )
    )
    assert out[0]["technologies"] == []


def test_cves_are_deduplicated_across_findings():
    out = aggregate_assets(
        rows(
            "a",
            F("high", cve_ids=["CVE-2020-0001", "CVE-2020-0002"]),
            F("high", cve_ids=["CVE-2020-0001"]),
        )
    )
    assert out[0]["cves"] == ["CVE-2020-0001", "CVE-2020-0002"]


def test_exploit_available_is_set_by_kev_or_exploitability():
    assert aggregate_assets(rows("a", F("high", cisa_kev=True)))[0]["exploit_available"]
    assert aggregate_assets(rows("a", F("high", exploitability="proven")))[0][
        "exploit_available"
    ]
    assert aggregate_assets(rows("a", F("high", exploitability="LIKELY")))[0][
        "exploit_available"
    ]


def test_exploit_available_stays_false_for_speculative_findings():
    out = aggregate_assets(rows("a", F("high", exploitability="unlikely"), F("low")))
    assert out[0]["exploit_available"] is False


def test_one_exploitable_finding_marks_the_whole_host():
    out = aggregate_assets(rows("a", F("low"), F("critical", cisa_kev=True), F("info")))
    assert out[0]["exploit_available"] is True


# ── host resolution ────────────────────────────────────────────────────────
def test_host_of_prefers_the_url_hostname():
    assert host_of("https://shop.acme.example/cart?x=1", "fallback") == "shop.acme.example"


def test_host_of_strips_a_port_from_a_bare_host():
    assert host_of("10.20.30.5:8080", None) == "10.20.30.5"


def test_host_of_falls_back_to_the_run_target_then_to_unknown():
    assert host_of("", "https://api.acme.example") == "https://api.acme.example"
    assert host_of("", "") == "unknown"
    assert host_of(None, None) == "unknown"


def test_empty_input_yields_no_assets():
    assert aggregate_assets([]) == []


# ── screenshots ────────────────────────────────────────────────────────────
def test_screenshot_is_attached_per_host_and_defaults_to_empty():
    out = aggregate_assets(
        rows("a.example", F("high")) + rows("b.example", F("high")),
        {"a.example": "/media/shot.png"},
    )
    by_host = {a["host"]: a for a in out}
    assert by_host["a.example"]["screenshot"] == "/media/shot.png"
    assert by_host["b.example"]["screenshot"] == ""
