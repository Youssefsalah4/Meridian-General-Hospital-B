CREATE TABLE "Staff" (
  "id" integer PRIMARY KEY,
  "name" varchar,
  "role" varchar,
  "auth_token" varchar
);

CREATE TABLE "Patients" (
  "id" integer PRIMARY KEY,
  "name" varchar,
  "blood_type" varchar,
  "urgency_level" varchar
);

CREATE TABLE "Blood_Inventory" (
  "id" integer PRIMARY KEY,
  "blood_type" varchar,
  "units_available" integer,
  "expiration_date" date
);

CREATE TABLE "Surgeries" (
  "id" integer PRIMARY KEY,
  "patient_id" integer,
  "surgeon_id" integer,
  "operating_room" varchar,
  "status" varchar,
  "scheduled_time" datetime,
  "end_time" datetime,
  FOREIGN KEY ("patient_id") REFERENCES "Patients" ("id"),
  FOREIGN KEY ("surgeon_id") REFERENCES "Staff" ("id")
);

CREATE TABLE "Blood_Allocations" (
  "id" integer PRIMARY KEY,
  "inventory_id" integer,
  "patient_id" integer,
  "authorized_by" integer,
  "units_allocated" integer,
  "allocation_time" datetime,
  "status" varchar,
  FOREIGN KEY ("inventory_id") REFERENCES "Blood_Inventory" ("id"),
  FOREIGN KEY ("patient_id") REFERENCES "Patients" ("id"),
  FOREIGN KEY ("authorized_by") REFERENCES "Staff" ("id")
);