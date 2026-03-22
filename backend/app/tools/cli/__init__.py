"""CLI security tool implementations.

Each tool wraps a free CLI binary (nmap, subfinder, etc.) via subprocess.
"""
from app.tools.cli.base_cli import BaseCLITool
from app.tools.cli.nmap_tool import NmapTool
from app.tools.cli.subfinder_tool import SubfinderTool
from app.tools.cli.httpx_tool import HttpxTool
from app.tools.cli.nuclei_tool import NucleiTool
from app.tools.cli.nikto_tool import NiktoTool
from app.tools.cli.ffuf_tool import FfufTool
from app.tools.cli.gobuster_tool import GobusterTool
from app.tools.cli.katana_tool import KatanaTool
from app.tools.cli.whatweb_tool import WhatWebTool
from app.tools.cli.theharvester_tool import TheHarvesterTool

ALL_CLI_TOOLS: list[type[BaseCLITool]] = [
    NmapTool,
    SubfinderTool,
    HttpxTool,
    NucleiTool,
    NiktoTool,
    FfufTool,
    GobusterTool,
    KatanaTool,
    WhatWebTool,
    TheHarvesterTool,
]

__all__ = [
    "BaseCLITool",
    "ALL_CLI_TOOLS",
    "NmapTool",
    "SubfinderTool",
    "HttpxTool",
    "NucleiTool",
    "NiktoTool",
    "FfufTool",
    "GobusterTool",
    "KatanaTool",
    "WhatWebTool",
    "TheHarvesterTool",
]
