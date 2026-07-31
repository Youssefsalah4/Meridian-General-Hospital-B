"""
mcp_server/notifications.py
Handles dynamic notifications pushing, such as tools/list_changed,
complying with the MCP protocol specification.
"""

import logging

logger = logging.getLogger("mcp_server")


async def notify_tools_changed(session) -> bool:
    """
    Sends a notifications/tools/list_changed message to the client session.
    Forces the client to re-request the list of tools.
    """
    if not session:
        logger.warning("No active session to notify.")
        return False 

    try:
        # Check if the session object has the standard send_tools_list_changed helper
        if hasattr(session, "send_tools_list_changed"):
            await session.send_tools_list_changed()
            logger.info("Sent tools/list_changed notification via SDK helper.")
            return True
        # Fallback to direct low-level notification send if helper is missing
        elif hasattr(session, "send_notification"):
            from mcp.types import Notification
            notification = Notification(method="notifications/tools/list_changed")
            await session.send_notification(notification)
            logger.info("Sent tools/list_changed notification via low-level session.")
            return True
        else:
            logger.warning("Session object does not support notification dispatch.")
            return False
    except Exception as e:
        logger.error(f"Failed to send tools/list_changed notification: {e}")
        return False
