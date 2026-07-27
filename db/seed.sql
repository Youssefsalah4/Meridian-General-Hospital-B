-- Insert Staff (Includes roles needed for Notifications and Elicitation)
INSERT INTO "Staff" (id, name, role, auth_token) VALUES
(1, 'Sarah Jenkins', 'Front Desk Nurse', 'token_nurse_123'),
(2, 'Dr. Marcus Webb', 'Attending Surgeon', 'token_surg_456'),
(3, 'Dr. Elena Rostova', 'Blood Bank Director', 'token_dir_789'),
(4, 'David Chen', 'Pharmacy Tech', 'token_pharm_101'),
(5, 'Dr. Amir Hassan', 'Attending Surgeon', 'token_surg_202');

-- Insert Patients (Includes a critical O- patient)
INSERT INTO "Patients" (id, name, blood_type, urgency_level) VALUES
(1, 'John Doe', 'A+', 'Low'),
(2, 'Jane Smith', 'O-', 'Critical'),
(3, 'Robert Ford', 'B-', 'Moderate'),
(4, 'Emily Clark', 'AB+', 'High'),
(5, 'Michael Scott', 'O+', 'Low');

-- Insert Blood Inventory (Notice the critically low O- supply)
INSERT INTO "Blood_Inventory" (id, blood_type, units_available, expiration_date) VALUES
(1, 'A+', 50, '2026-08-15'),
(2, 'O-', 2, '2026-07-30'), 
(3, 'B-', 20, '2026-08-10'),
(4, 'AB+', 15, '2026-08-22'),
(5, 'O+', 40, '2026-08-05');

-- Insert Surgeries (Includes different statuses and timeframes)
INSERT INTO "Surgeries" (id, patient_id, surgeon_id, operating_room, status, scheduled_time, end_time) VALUES
(1, 2, 2, 'OR-1', 'Scheduled', '2026-07-28 08:00:00', '2026-07-28 12:00:00'),
(2, 4, 5, 'OR-2', 'In Progress', '2026-07-27 16:00:00', '2026-07-27 19:00:00'),
(3, 1, 2, 'OR-1', 'Completed', '2026-07-26 09:00:00', '2026-07-26 11:00:00'),
(4, 3, 5, 'OR-3', 'Scheduled', '2026-07-29 10:00:00', '2026-07-29 14:00:00'),
(5, 5, 2, 'OR-2', 'Cancelled', '2026-07-25 14:00:00', '2026-07-25 15:30:00');

-- Insert Blood Allocations (Shows historical and pending approvals)
INSERT INTO "Blood_Allocations" (id, inventory_id, patient_id, authorized_by, units_allocated, allocation_time, status) VALUES
(1, 2, 2, 3, 2, '2026-07-27 10:30:00', 'Approved'),
(2, 4, 4, 2, 1, '2026-07-27 15:00:00', 'Approved'),
(3, 1, 1, 2, 1, '2026-07-26 08:30:00', 'Completed'),
(4, 3, 3, 5, 2, '2026-07-27 11:00:00', 'Pending'),
(5, 5, 5, 2, 1, '2026-07-25 13:00:00', 'Cancelled');