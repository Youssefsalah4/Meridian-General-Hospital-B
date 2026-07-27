import sqlite3
import os

# Define the path to where the SQLite database file will live
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'meridian.db')

def get_connection():
    """Establishes a secure connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows us to access columns by their names
    return conn

def get_patient(patient_id):
    """Fetches a patient's vitals and urgency level (Read-only tool)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM "Patients" WHERE id = ?', (patient_id,))
    patient = cursor.fetchone()
    conn.close()
    return dict(patient) if patient else None

def check_blood_inventory(blood_type):
    """Checks the available units of a specific blood type (Read-only tool)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM "Blood_Inventory" WHERE blood_type = ?', (blood_type,))
    inventory = cursor.fetchone()
    conn.close()
    return dict(inventory) if inventory else None

def allocate_blood(inventory_id, patient_id, authorized_by, units, allocation_time):
    """Authorizes a blood transfer (State-change tool requiring Elicitation)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Insert the allocation record
    cursor.execute('''
        INSERT INTO "Blood_Allocations" 
        (inventory_id, patient_id, authorized_by, units_allocated, allocation_time, status) 
        VALUES (?, ?, ?, ?, ?, 'Approved')
    ''', (inventory_id, patient_id, authorized_by, units, allocation_time))
    
    # Deduct the units from the inventory
    cursor.execute('''
        UPDATE "Blood_Inventory" 
        SET units_available = units_available - ? 
        WHERE id = ?
    ''', (units, inventory_id))
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Successfully allocated {units} units."}

def check_operating_room_availability(operating_room, scheduled_time, end_time):
    """Server-side validation to prevent double-booking (Defensive Design)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check for overlapping surgeries in the same room
    cursor.execute('''
        SELECT * FROM "Surgeries" 
        WHERE operating_room = ? 
        AND status != 'Cancelled'
        AND (
            (scheduled_time <= ? AND end_time > ?) OR
            (scheduled_time < ? AND end_time >= ?)
        )
    ''', (operating_room, end_time, scheduled_time, end_time, scheduled_time))
    
    conflict = cursor.fetchone()
    conn.close()
    
    return conflict is None  # Returns True if available, False if double-booked