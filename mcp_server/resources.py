"""
mcp_server/resources.py
Implements static read-only resources for Meridian General Hospital.
Exposes the Emergency Transfusion Policy document.
"""

from typing import List, Optional
from mcp.types import Resource, TextResourceContents

POLICY_URI = "resource://policy/emergency-transfusion"
POLICY_NAME = "Emergency Transfusion Policy"
POLICY_DESCRIPTION = "Meridian General Hospital guidelines and authorization rules for urgent blood allocation."
POLICY_MIME_TYPE = "text/markdown"

POLICY_CONTENT = """# Meridian General Hospital (MGH-POL-419)
## Emergency Transfusion Policy & Blood Usage Guidelist

1. **Objective**
   Define safety guards for administering uncrossmatched blood products during critical emergencies where waiting for full compatibility testing poses an immediate threat to patient survival.

2. **Standard Protocols**
   * Pre-transfusion testing must be initiated immediately upon patient admission.
   * If emergency transfusion is required BEFORE blood typing completes, **O-negative (scarce)** red blood cells shall be released.
   * Once patient blood type is known, the patient must be switched to type-specific blood immediately to conserve O-negative stock.

3. **O-Inverse Inventory Guard (Directors' Sign-off)**
   * O-negative blood is the universal donor, but is extremely scarce.
   * If O-negative inventory falls to **2 units or fewer**:
     * Any allocation of O-negative units requires **explicit elicitation confirmation** (sign-off) from the Blood Bank Director (Role: `Blood Bank Director`).
     * Attending Surgeons cannot auto-approve allocation when blood inventory <= 2.
     * All non-elicitation sessions (where the client lacks human-in-the-loop capability) will be blocked from allocating O-negative blood under low-stock conditions.

4. **Transfusion Authority Matrix**
   * **Front Desk Nurse**: Permitted to read policy docs, client reports, and view vitals. Unauthorized to order blood allocation.
   * **Attending Surgeon**: Authorized to order blood allocation, subject to clinical guidelines and Elicitation checks.
   * **Blood Bank Director**: Authorized to order blood release, approve/deny clinical overrides, and certify safety.
"""


def list_resources() -> List[Resource]:
    """
    Returns the list of available static resources exposed by this server.
    """
    return [
        Resource(
            uri=POLICY_URI,
            name=POLICY_NAME,
            description=POLICY_DESCRIPTION,
            mimeType=POLICY_MIME_TYPE
        )
    ]


def read_resource(uri: str) -> Optional[List[TextResourceContents]]:
    """
    Reads the content of an exposed resource by its unique URI.
    """
    if uri == POLICY_URI:
        return [
            TextResourceContents(
                uri=POLICY_URI,
                mimeType=POLICY_MIME_TYPE,
                text=POLICY_CONTENT
            )
        ]
    return None
