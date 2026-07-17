"""Nmap port scanning tool."""
import xml.etree.ElementTree as ET
from typing import Any

from redweaver_engine.tools.base import ToolCategory
from redweaver_engine.tools.cli.base_cli import BaseCLITool


class NmapTool(BaseCLITool):
    name = "nmap_scan"
    description = (
        "Port scan a target host or IP using nmap. "
        "Returns open ports, services, and versions. "
        "Options: scan_type='quick'|'service'|'full' (default: service). "
        "'quick'=top-100 fast; 'service'=top-1000 with -sV version + -sC default scripts (recommended, deep); "
        "'full'=all 65535 ports with -sV version detection."
    )
    category = ToolCategory.NETWORK
    binary_name = "nmap"
    default_timeout = 600

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        cmd = ["nmap", "-oX", "-"]  # XML output to stdout
        # Default to a deep service scan: top-1000 ports + version + default scripts.
        scan_type = options.get("scan_type", "service")
        if scan_type == "full":
            # All 65535 ports with version detection.
            cmd.extend(["-sV", "-T4", "-p-"])
        elif scan_type == "quick":
            # Fast triage: top-100 ports, no version detection.
            cmd.extend(["-T4", "-F"])
        else:  # service (default): deep top-1000 scan with -sV + -sC
            cmd.extend(["-sV", "-sC", "-T4", "--top-ports", "1000"])
        cmd.append(target.strip())
        return cmd

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> dict[str, Any]:
        try:
            root = ET.fromstring(stdout)
        except ET.ParseError:
            return {"raw_output": stdout[:3000], "error": "Failed to parse nmap XML"}

        hosts: list[dict[str, Any]] = []
        for host in root.findall(".//host"):
            addr_el = host.find('.//address[@addrtype="ipv4"]')
            if addr_el is None:
                addr_el = host.find(".//address")
            ip = addr_el.get("addr", "unknown") if addr_el is not None else "unknown"

            ports: list[dict[str, Any]] = []
            for port_el in host.findall(".//port"):
                state_el = port_el.find("state")
                svc_el = port_el.find("service")
                # Build the most precise version string nmap gives us
                # (product + version + extrainfo), used downstream for CVE matching.
                product = svc_el.get("product", "") if svc_el is not None else ""
                version = svc_el.get("version", "") if svc_el is not None else ""
                extrainfo = svc_el.get("extrainfo", "") if svc_el is not None else ""
                version_full = " ".join(p for p in (product, version, extrainfo) if p).strip()
                # Capture -sC default-script output so deep scans aren't discarded.
                scripts: dict[str, str] = {}
                for script_el in port_el.findall("script"):
                    sid = script_el.get("id", "")
                    out = (script_el.get("output", "") or "").strip()
                    if sid and out:
                        scripts[sid] = out[:600]
                entry: dict[str, Any] = {
                    "port": port_el.get("portid", ""),
                    "protocol": port_el.get("protocol", ""),
                    "state": state_el.get("state", "") if state_el is not None else "",
                    "service": svc_el.get("name", "") if svc_el is not None else "",
                    "product": product,
                    "version": version_full or version,
                }
                if scripts:
                    entry["scripts"] = scripts
                ports.append(entry)

            # Host-level scripts (e.g. smb-os-discovery) attach under hostscript.
            host_scripts: dict[str, str] = {}
            for script_el in host.findall(".//hostscript/script"):
                sid = script_el.get("id", "")
                out = (script_el.get("output", "") or "").strip()
                if sid and out:
                    host_scripts[sid] = out[:600]

            host_entry: dict[str, Any] = {"ip": ip, "ports": ports}
            if host_scripts:
                host_entry["host_scripts"] = host_scripts
            hosts.append(host_entry)

        return {"hosts": hosts, "host_count": len(hosts)}
