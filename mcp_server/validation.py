"""
mcp_server/validation.py
Defensive validation rules for Meridian Surgical & Blood Bank actions.
Contains server-side business logic validation independent of JSON schemas.
"""

from typing import Dict, Any, Tuple
import datetime
from database import get_connection, check_operating_room_availability, get_patient, check_blood_inventory

# Standard blood compatibility mapping: key = recipient, value = compatible donor types
BLOOD_COMPATIBILITY = {
    "O-": {"O-"},
    "O+": {"O-", "O+"},
    "A-": {"O-", "A-"},
    "A+": {"O-", "O+", "A-", "A+"},
    "B-": {"O-", "B-"},
    "B+": {"O-", "O+", "B-", "B+"},
    "AB-": {"O-", "A-", "B-", "AB-"},
    "AB+": {"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"}
}


def validate_surgery_scheduling(patient_id: int, surgeon_id: int, operating_room: str, scheduled_time_str: str, end_time_str: str) -> Tuple[bool, str]:
    """
    Validates surgery scheduling inputs and checks for operating room booking conflicts.
    """
    try:
        # Enforce positive IDs
        if patient_id <= 0 or surgeon_id <= 0:
            return False, "Patient ID and Surgeon ID must be positive integers."

        # Parse and validate times
        try:
            scheduled_time = datetime.datetime.fromisoformat(scheduled_time_str.split('Z')[0])
            end_time = datetime.datetime.fromisoformat(end_time_str.split('Z')[0])
        except ValueError:
            return False, "Invalid ISO datetime format for scheduled_time or end_time."

        if scheduled_time >= end_time:
            return False, "Surgery scheduled time must be earlier than the end time."

        if scheduled_time < datetime.datetime.now() - datetime.timedelta(days=365):
            return False, "Scheduled surgery time cannot be too far in the past."

        # Check surgeon existence
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT role FROM "Staff" WHERE id = ?', (surgeon_id,))
        staff = cursor.fetchone()
        conn.close()
        
        if not staff:
            return False, f"Surgeon with ID {surgeon_id} not found in staff directory."
        
        if staff["role"] != "Attending Surgeon":
            return False, f"Staff member {surgeon_id} is not an Attending Surgeon (Role: {staff['role']})."

        # Check operating room availability (Defensive Conflict Guard)
        is_available = check_operating_room_availability(operating_room, scheduled_time_str, end_time_str)
        if not is_available:
            return False, f"Operating room '{operating_room}' is already booked or overlaps list of surgeries."

        return True, "Valid"
    except Exception as e:
        return False, f"Internal validation error: {str(e)}"


def validate_blood_allocation(inventory_id: int, patient_id: int, units: int) -> Tuple[bool, str]:
    """
    Ensures allocated blood units are available, positive, and matches recipient compatibility.
    """
    try:
        if units <= 0:
            return False, "Allocated blood units must be greater than zero."

        # Fetch patient details
        patient = get_patient(patient_id)
        if not patient:
            return False, f"Patient with ID {patient_id} does not exist."

        # Fetch inventory details
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM "Blood_Inventory" WHERE id = ?', (inventory_id,))
        inventory = cursor.fetchone()
        conn.close()

        if not inventory:
            return False, f"Blood inventory item with ID {inventory_id} does not exist."

        # Check stock limits
        available = inventory["units_available"]
        if units > available:
            return False, f"Insufficient stock: requested {units} units, but only {available} units are available."

        # Check compatibility
        patient_blood = patient["blood_type"]
        donor_blood = inventory["blood_type"]
        
        allowed_donors = BLOOD_COMPATIBILITY.get(patient_blood, set())
        if donor_blood not in allowed_donors:
            return False, f"Incompatible transfusion: Patient is {patient_blood}, but donor units are {donor_blood}."

        return True, "Valid"
    except Exception as e:
        return False, f"Internal validation error: {str(e)}"
