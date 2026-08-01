"""
mcp_server/tools.py
Exposes the MCP tools for Meridian Surgical & Blood Bank using the @mcp.tool() decorator.
Integrates defensive validation, authorization, and protocol features (Elicitation & Progress).
"""

from mcp.types import SamplingMessage, TextContent
import sys
import os
import asyncio
from mcp.server.fastmcp import FastMCP, Context
import database
from auth import is_tool_authorized, authenticate_staff, get_allowed_tools_for_role
from validation import validate_surgery_scheduling, validate_blood_allocation

# Initialize the FastMCP server instance
mcp = FastMCP("Meridian-General-Hospital")


def _get_current_token() -> str:
    """
    Retrieves the authenticating staff token from environment variables.
    In stdio, the parent client sets this when spawning the server process.
    """
    return os.getenv("STAFF_TOKEN", "token_nurse_123")



async def get_patient_vitals(patient_id: int) -> dict:
    """
    Expositions tool to fetch patient vitals, urgency levels, and demographics. (Read-only)
    """
    token = _get_current_token()
    if not is_tool_authorized(token, "get_patient_vitals"):
        raise PermissionError(f"Staff member is unauthorized to execute get_patient_vitals.")

    vitals = database.get_patient(patient_id)
    if not vitals:
        return {"status": "error", "message": f"Patient with ID {patient_id} not found."}
    return dict(vitals)



async def check_blood_inventory(blood_type: str) -> dict:
    """
    Query the available capacity and expiration of specific blood types. (Read-only)
    """
    token = _get_current_token()
    if not is_tool_authorized(token, "check_blood_inventory"):
        raise PermissionError(f"Staff member is unauthorized to execute check_blood_inventory.")

    inv = database.check_blood_inventory(blood_type)
    if not inv:
        return {"status": "error", "message": f"Blood type '{blood_type}' not found in inventory."}
    return dict(inv)



async def allocate_blood(
    inventory_id: int,
    patient_id: int,
    authorized_by: int,
    units: int,
    allocation_time: str,
    ctx: Context = None
) -> dict:
    """
    Authorizes blood release and transaction. Allocating O- negative requires Director approval.
    """
    token = _get_current_token()
    if not is_tool_authorized(token, "allocate_blood"):
        raise PermissionError(f"Staff member is unauthorized to execute allocate_blood.")

    # 1. Server-side validation
    ok, msg = validate_blood_allocation(inventory_id, patient_id, units)
    if not ok:
        raise ValueError(f"Transfusion validation rejected: {msg}")

    # 2. Scarcity and blood type elicitation override logic
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT blood_type, units_available FROM "Blood_Inventory" WHERE id = ?', (inventory_id,))
    inv = cursor.fetchone()
    conn.close()

    if inv and inv["blood_type"] == "O-" and inv["units_available"] <= 2:
        # Check if the client session declared elicitation capability
        session = getattr(ctx, "session", None) if ctx else None

       

        # Determine capability: does client declare elicitation support?
        has_elicitation = False
        if session and getattr(session, "capabilities", None):
            has_elicitation = getattr(session.capabilities, "elicitation", None) is not None
        
        # Determine capability: does client declare elicitation support?
        has_elicitation = False
        if session and getattr(session, "client_params", None):
            client_caps = getattr(session.client_params, "capabilities", None)
            has_elicitation = client_caps is not None and getattr(client_caps, "elicitation", None) is not None

        if not has_elicitation:
            # Shield scarce blood products if client cannot run human elicitation
            raise PermissionError(
                "Allocation blocked: Requesting O-negative units under scarcity (<= 2 units available) "
                "requires Blood Bank Director approval via Elicitation. Client lacks elicitation support."
            )

        # Trigger human elicitation call under O- scarcity
       # Trigger human elicitation call under O- scarcity, using the
        # session's dedicated elicit() method (not the generic
        # send_request, which expects a typed object, not a raw string).
        try:
            res = await session.elicit(
                message=f"Director override required: Releasing {units} unit(s) of scarce O- blood to Patient {patient_id}.",
                requestedSchema={
                    "type": "object",
                    "properties": {
                        "director_override": {
                            "type": "string",
                            "description": "Type 'approve' or 'deny' to confirm command.",
                            "enum": ["approve", "deny"]
                        }
                    },
                    "required": ["director_override"]
                }
            )
            if res.action != "accept":
                return {"status": "denied", "message": "Allocation denied by Blood Bank Director."}
        except Exception as e:
            raise PermissionError(f"Elicitation transaction aborted: {str(e)}")

    # Proceed to allocate
    return database.allocate_blood(inventory_id, patient_id, authorized_by, units, allocation_time)



async def schedule_surgery(
    patient_id: int,
    surgeon_id: int,
    operating_room: str,
    scheduled_time: str,
    end_time: str
) -> dict:
    """
    Schedules a new surgery case, routing conflicts defensively from double booking.
    """
    token = _get_current_token()
    if not is_tool_authorized(token, "schedule_surgery"):
        raise PermissionError(f"Staff member is unauthorized to execute schedule_surgery.")

    # Server-side validation
    ok, msg = validate_surgery_scheduling(patient_id, surgeon_id, operating_room, scheduled_time, end_time)
    if not ok:
        raise ValueError(f"Surgery scheduling rejected: {msg}")

    # Database insertion
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO "Surgeries" 
        (patient_id, surgeon_id, operating_room, status, scheduled_time, end_time) 
        VALUES (?, ?, ?, 'Scheduled', ?, ?)
    ''', (patient_id, surgeon_id, operating_room, scheduled_time, end_time))
    conn.commit()
    conn.close()

    return {"status": "success", "message": f"Surgery successfully scheduled in {operating_room}."}



async def run_crossmatch_compatibility(patient_id: int, ctx: Context = None) -> dict:
    """
    Performs antibody laboratory check on patient sample, streaming progress checkpoints.
    """
    token = _get_current_token()
    if not is_tool_authorized(token, "run_crossmatch_compatibility"):
        raise PermissionError(f"Staff member is unauthorized to execute run_crossmatch_compatibility.")

    patient = database.get_patient(patient_id)
    if not patient:
        return {"status": "error", "message": f"Patient ID {patient_id} does not exist."}

    steps = [
        (20, "Initiating antibody screening on patient blood sample..."),
        (50, "Incubating donor cells with patient serum..."),
        (85, "Centrifuging and checking for agglutination (clumping)..."),
        (100, "Assay completed. No cross-reactivity detected. Blood units certified compatible.")
    ]

    # Handle progressive updates if a progress token and context session exist
    for pct, desc in steps:
        await asyncio.sleep(0.3)
        if ctx and hasattr(ctx, "session") and ctx.session:
            # Check if there is an active request/progress context in FastMCP
            # Standard FastMCP Context helper for progress updates
            if hasattr(ctx, "report_progress"):
                await ctx.report_progress(pct, 100)
            elif hasattr(ctx.session, "send_notification"):
                # Fallback to direct progress notification stream
                try:
                    await ctx.session.send_notification(
                        "notifications/progress",
                        {
                            "progressToken": getattr(ctx, "progress_token", "default_token"),
                            "progress": pct,
                            "total": 100
                        }
                    )
                except Exception:
                    pass

    return {
        "status": "success",
        "patient_name": patient["name"],
        "blood_type": patient["blood_type"],
        "compatibility": "Compatible",
        "certified_by": "Automated MCP Assay"
    }
    
    
    
    
    
async def generate_surgical_handoff(
    surgery_id: int,
    ctx: Context
) -> dict:
    """
    Demonstrates MCP Sampling.
    Requests the client's model to generate a surgical handoff summary.
    """

    conn = database.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.name,
            p.blood_type,
            p.urgency_level,
            s.operating_room,
            s.scheduled_time,
            st.name as surgeon_name
        FROM "Surgeries" s
        JOIN "Patients" p ON s.patient_id = p.id
        JOIN "Staff" st ON s.surgeon_id = st.id
        WHERE s.id = ?
    """, (surgery_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "status": "error",
            "message": "Surgery not found."
        }

    session = getattr(ctx, "session", None)

    if not session:
        return {
            "status": "error",
            "message": "No active MCP session."
        }

    try:
        prompt_text = f"""
Generate a professional surgical handoff summary.

Patient: {row["name"]}
Blood Type: {row["blood_type"]}
Urgency: {row["urgency_level"]}
Surgeon: {row["surgeon_name"]}
Operating Room: {row["operating_room"]}
Scheduled Time: {row["scheduled_time"]}

Include:
1. Patient Summary
2. Pre-operative Status
3. Recommended Handoff Destination
4. Follow-up Notes
"""

        response = await session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text),
                )
            ],
            max_tokens=300,
        )

        summary_text = response.content.text if response.content.type == "text" else str(response.content)

        return {
            "status": "success",
            "sampling_used": True,
            "response": summary_text
        }

    except Exception as e:

        return {
            "status": "error",
            "sampling_used": False,
            "message": str(e)
        }
        
# --- Role-based conditional registration -------------------------------
_ALL_TOOLS = {
    "get_patient_vitals": get_patient_vitals,
    "check_blood_inventory": check_blood_inventory,
    "allocate_blood": allocate_blood,
    "schedule_surgery": schedule_surgery,
    "run_crossmatch_compatibility": run_crossmatch_compatibility,
     "generate_surgical_handoff": generate_surgical_handoff
       
}

_staff = authenticate_staff(_get_current_token())
_role = _staff["role"] if _staff else None
_allowed_tool_names = get_allowed_tools_for_role(_role)

for _name, _fn in _ALL_TOOLS.items():
    if _name in _allowed_tool_names:
        mcp.tool()(_fn)
