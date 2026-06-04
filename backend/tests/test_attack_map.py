"""Unit tests for finding -> MITRE ATT&CK mapping + Navigator layer (no DB)."""
from apps.findings.attack_map import navigator_layer, techniques_for


def test_xss_maps_to_techniques():
    ids = [t["id"] for t in techniques_for({"title": "Reflected XSS in search", "description": ""})]
    assert "T1190" in ids


def test_ssh_maps_to_bruteforce_and_discovery():
    ids = [t["id"] for t in techniques_for({"title": "Open SSH port 22", "description": ""})]
    assert "T1110" in ids and "T1046" in ids


def test_unknown_falls_back():
    ids = [t["id"] for t in techniques_for({"title": "something weird", "description": ""})]
    assert ids  # never empty


class _F:
    def __init__(self, title, severity):
        self.title = title
        self.severity = severity
        self.description = ""


def test_navigator_layer_is_valid():
    layer = navigator_layer(
        type("R", (), {"target": "example.com"})(),
        [_F("Open SSH port 22", "low"), _F("SQL injection", "high")],
    )
    assert layer["domain"] == "enterprise-attack"
    assert layer["versions"]["layer"]
    assert len(layer["techniques"]) >= 2
    assert all("techniqueID" in t for t in layer["techniques"])
