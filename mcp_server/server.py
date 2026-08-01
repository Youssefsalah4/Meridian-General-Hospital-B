"""
mcp_server/server.py
Main entry point for the Meridian Surgical & Blood Bank MCP Server.
Wires up resources, prompts, tools, and starts the transport listener.
"""

import sys
import os
import logging

# Ensure local imports work fine
sys.path.append(os.path.dirname(__file__))

from tools import mcp
from resources import POLICY_CONTENT
from prompts import get_prompt
from transport import start_mcp_server

# Set up server-side logging formatting
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_server")


# --- Register MCP Resources using FastMCP Decorator ---
@mcp.resource("resource://policy/emergency-transfusion")
def emergency_transfusion_policy() -> str:
    """
    Exposes the Emergency Transfusion Policy and authorization matrices for clinical consultation.
    """
    logger.info("Transfusion policy resource requested by client.")
    return POLICY_CONTENT


# --- Register MCP Prompts using FastMCP Decorator ---
@mcp.prompt()
def draft_surgical_transfer_summary(surgery_id: int) -> str:
    """
    Drafts a parameterized case transfer and handoff summary for a completed surgery.
    """
    logger.info(f"Surgical transfer summary prompt requested for surgery case ID {surgery_id}.")
    
    # We call our prompts module helper to generate the content dynamically from SQL DB
    prompt_result = get_prompt("draft_surgical_transfer_summary", {"surgery_id": str(surgery_id)})
    if not prompt_result or not prompt_result.messages:
        return f"Error: Unable to generate prompt for Surgery ID {surgery_id}."
    
    # Extract structural prompt body
    prompt_message = prompt_result.messages[0]
    return prompt_message.content.text


# --- Server Startup Execution ---
def main():
    logger.info("Initializing Meridian General Hospital MCP Server core...")
    # Declare capability negotiation features, verify seed file exists
    db_file = os.path.join(os.path.dirname(__file__), '..', 'db', 'meridian.db')
    if not os.path.exists(db_file):
        logger.warning(f"Database file not found at '{db_file}'. Running setup script is recommended first.")
    
    try:
        # Start server listening loop using transport configuration
        start_mcp_server(mcp)
    except Exception as e:
        logger.critical(f"MCP Server crashed during startup loop: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
