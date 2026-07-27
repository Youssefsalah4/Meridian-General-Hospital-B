import sqlite3
import os

# Define file paths based on your repository structure
DB_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(DB_DIR, 'meridian.db')
SCHEMA_PATH = os.path.join(DB_DIR, 'schema.sql')
SEED_PATH = os.path.join(DB_DIR, 'seed.sql')

def initialize_database():
    # Remove the old database if it exists so we start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Removed existing meridian.db")

    # Connect to (and create) the new database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Read and execute the schema.sql file
    with open(SCHEMA_PATH, 'r') as f:
        schema_script = f.read()
    cursor.executescript(schema_script)
    print("Schema created successfully.")

    # Read and execute the seed.sql file
    with open(SEED_PATH, 'r') as f:
        seed_script = f.read()
    cursor.executescript(seed_script)
    print("Seed data inserted successfully.")

    conn.commit()
    conn.close()
    print(f"Database ready at: {DB_PATH}")

if __name__ == '__main__':
    initialize_database()