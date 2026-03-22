"""Nmap port scanning tool."""
import xml.etree.ElementTree as ET
from typing import Any

from app.tools.base import ToolCategory
from app.tools.cli.base_cli import BaseCLITool


class NmapTool(BaseCLITool):
    name = "nmap_scan"
    description = (
        "Port scan a target host or IP using nmap. "
        "Returns open ports, services, and versions. "
        "Options: scan_type='quick'|'full'|'service' (default: quick)."
    )
    category = ToolCategory.NETWORK
    binary_name = "nmap"
    default_timeout = 600

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        cmd = ["nmap", "-oX", "-"]  # XML output to stdout
        scan_type = options.get("scan_type", "quick")
        if scan_type == "full":
            cmd.extend(["-T4", "-p-"])
        elif scan_type == "service":
            cmd.extend(["-sV", "-T4", "-F"])
        else:  # quick
            cmd.extend(["-T4", "-F"])
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

            ports: list[dict[str, str]] = []
            for port_el in host.findall(".//port"):
                state_el = port_el.find("state")
                svc_el = port_el.find("service")
                ports.append({
                    "port": port_el.get("portid", ""),
                    "protocol": port_el.get("protocol", ""),
                    "state": state_el.get("state", "") if state_el is not None else "",
                    "service": svc_el.get("name", "") if svc_el is not None else "",
                    "version": svc_el.get("version", "") if svc_el is not None else "",
                })
            hosts.append({"ip": ip, "ports": ports})

        return {"hosts": hosts, "host_count": len(hosts)}
