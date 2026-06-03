"""CLI security tool implementations.

Each tool wraps a free CLI binary (nmap, subfinder, etc.) via subprocess.
"""
from redweaver_engine.tools.cli.base_cli import BaseCLITool
from redweaver_engine.tools.cli.nmap_tool import NmapTool
from redweaver_engine.tools.cli.subfinder_tool import SubfinderTool
from redweaver_engine.tools.cli.httpx_tool import HttpxTool
from redweaver_engine.tools.cli.nuclei_tool import NucleiTool
from redweaver_engine.tools.cli.nikto_tool import NiktoTool
from redweaver_engine.tools.cli.ffuf_tool import FfufTool
from redweaver_engine.tools.cli.gobuster_tool import GobusterTool
from redweaver_engine.tools.cli.katana_tool import KatanaTool
from redweaver_engine.tools.cli.whatweb_tool import WhatWebTool
from redweaver_engine.tools.cli.theharvester_tool import TheHarvesterTool

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
