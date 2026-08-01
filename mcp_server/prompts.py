"""
mcp_server/prompts.py
Registers and formats parameterized prompt templates for Meridian General Hospital.
"""

from typing import List, Dict, Any, Optional
from mcp.types import Prompt, PromptArgument, GetPromptResult, PromptMessage, TextContent
from database import get_connection

PROMPT_NAME = "draft_surgical_transfer_summary"
PROMPT_DESC = "Generates a structured medical handoff summary for a completed or scheduled surgery."


def list_prompts() -> List[Prompt]:
    """
    Exposes parameterized prompts that the server supports.
    """
    return [
        Prompt(
            name=PROMPT_NAME,
            description=PROMPT_DESC,
            arguments=[
                PromptArgument(
                    name="surgery_id",
                    description="The numeric ID of the surgical case to summarize",
                    required=True
                )
            ]
        )
    ]


def get_prompt(name: str, arguments: Dict[str, str]) -> Optional[GetPromptResult]:
    """
    Resolves the requested prompt template parameter inputs and produces messages for the model.
    """
    if name != PROMPT_NAME:
        return None

    surgery_id_str = arguments.get("surgery_id")
    if not surgery_id_str:
        raise ValueError("Missing required prompt argument: surgery_id")

    try:
        surgery_id = int(surgery_id_str)
    except ValueError:
        raise ValueError(f"surgery_id must be a numeric integer, got {surgery_id_str}")

    # Fetch surgery details from DB to build a rich contextual prompt
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            s.id AS surgery_id,
            s.operating_room,
            s.status,
            s.scheduled_time,
            s.end_time,
            p.name AS patient_name,
            p.blood_type AS patient_blood,
            p.urgency_level,
            st.name AS surgeon_name
        FROM "Surgeries" s
        JOIN "Patients" p ON s.patient_id = p.id
        JOIN "Staff" st ON s.surgeon_id = st.id
        WHERE s.id = ?
    ''', (surgery_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        context_body = f"Surgery ID {surgery_id} not found in the database. Please request patient info from user."
    else:
        context_body = (
            f"Case Reference: Surgery ID {row['surgery_id']}\n"
            f"Patient: {row['patient_name']} (Blood Type: {row['patient_blood']}, Urgency: {row['urgency_level']})\n"
            f"Surgeon: {row['surgeon_name']}\n"
            f"Operating Room: {row['operating_room']}\n"
            f"Scheduled: {row['scheduled_time']} to {row['end_time']}\n"
            f"Current Case Status: {row['status']}"
        )

    # Return standard PromptMessage with TextContent
    system_text = (
        "You are an expert clinical documentation assistant. Draft a professional, secure "
        "Surgical Transfer Summary based on the provided Case Reference. Ensure strict adherence "
        "to patient privacy guidelines (no external sharing) and medical formatting norms."
    )
    user_text = (
        f"Case Details:\n"
        f"==========================\n"
        f"{context_body}\n"
        f"==========================\n\n"
        f"Please draft a structured handoff report including:\n"
        f"1. Handoff Summary Header (Patient and Case Reference details).\n"
        f"2. Pre-operative Status & Setup.\n"
        f"3. Intended Post-operative Handoff Destination (e.g. ICU or general ward based on urgency)."
    )

    return GetPromptResult(
        description=f"Surgical Transfer Summary prompt for Surgery ID {surgery_id}",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=f"System Instruction: {system_text}\n\nUser Request: {user_text}")
            )
        ]
    )
