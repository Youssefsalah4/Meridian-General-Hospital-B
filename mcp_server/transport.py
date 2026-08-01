"""
mcp_server/transport.py
Configures and launches the MCP transport layers (stdio for local, SSE for remote).
Supports reading MCP_TRANSPORT environment variables to determine target transport.
"""

import os
import sys
import logging
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp_server")


def start_mcp_server(mcp_instance: FastMCP):
    """
    Starts the given FastMCP instance checking target transport (stdio or sse).
    """
    transport_mode = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()

    if transport_mode == "stdio":
        logger.info("Initializing MCP Server over standard I/O (stdio) transport channel.")
        # FastMCP.run() executes the async loop over stdio by default
        mcp_instance.run(transport="stdio")

    elif transport_mode in ("http", "sse"):
     port_env = os.getenv("MCP_SERVER_PORT", "8000")
     try:
        port = int(port_env)
     except ValueError:
        port = 8000

    # This SDK's FastMCP.run() doesn't accept host/port directly —
    # they're set on the instance's settings before calling run().
     mcp_instance.settings.port = port
     mcp_instance.settings.host = "127.0.0.1"

     logger.info(f"Initializing MCP Server over Server-Sent Events (SSE) HTTP tunnel on port {port}.")
     mcp_instance.run(transport="sse")
    else:
        logger.error(f"Unknown transport configuration '{transport_mode}'. Falling back to stdio.")
        mcp_instance.run(transport="stdio")
