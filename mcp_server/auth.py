"""
mcp_server/auth.py
Authentication & Role-Based Access Control (RBAC) for Meridian General Hospital MCP Server.

Validates staff auth tokens against the database / staff seed and maps staff roles
to visible tool permissions.
"""

from typing import Dict, Any, List, Optional
import os
import sys

# Add database path helper if needed
sys.path.append(os.path.dirname(__file__))
from database import get_connection

# Define Tool Access Matrix by Role
READ_ONLY_TOOLS = ["get_patient_vitals", "check_blood_inventory"]
SURGICAL_TOOLS = ["allocate_blood", "schedule_surgery", "run_crossmatch_compatibility"]
FULL_TOOL_SET = READ_ONLY_TOOLS + SURGICAL_TOOLS

ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "Front Desk Nurse": READ_ONLY_TOOLS,
    "Pharmacy Tech": READ_ONLY_TOOLS,
    "Attending Surgeon": FULL_TOOL_SET,
    "Blood Bank Director": FULL_TOOL_SET,
}

# Default static lookup fallback for offline/test environments
TOKEN_STAFF_MAP = {
    "token_nurse_123": {"id": 1, "name": "Sarah Jenkins", "role": "Front Desk Nurse"},
    "token_surg_456": {"id": 2, "name": "Dr. Marcus Webb", "role": "Attending Surgeon"},
    "token_dir_789": {"id": 3, "name": "Dr. Elena Rostova", "role": "Blood Bank Director"},
    "token_pharm_101": {"id": 4, "name": "David Chen", "role": "Pharmacy Tech"},
    "token_surg_202": {"id": 5, "name": "Dr. Amir Hassan", "role": "Attending Surgeon"},
}


def authenticate_staff(auth_token: str) -> Optional[Dict[str, Any]]:
    """
    Authenticates a staff token against the SQLite database with fallback to static map.
    Returns staff record dictionary or None if invalid.
    """
    if not auth_token:
        return None

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM "Staff" WHERE auth_token = ?', (auth_token,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
    except Exception:
        pass

    # Fallback to token dictionary
    if auth_token in TOKEN_STAFF_MAP:
        staff_info = TOKEN_STAFF_MAP[auth_token].copy()
        staff_info["auth_token"] = auth_token
        return staff_info

    return None


def get_allowed_tools_for_role(role: str) -> List[str]:
    """
    Returns the list of tool names permitted for the given staff role.
    Defaults to read-only tools if role is unknown.
    """
    return ROLE_PERMISSIONS.get(role, READ_ONLY_TOOLS)


def is_tool_authorized(auth_token: str, tool_name: str) -> bool:
    """
    Checks if a given staff token is authorized to execute a specific tool.
    """
    staff = authenticate_staff(auth_token)
    if not staff:
        return False
    allowed_tools = get_allowed_tools_for_role(staff["role"])
    return tool_name in allowed_tools
