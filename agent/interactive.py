"""
agent/interactive.py
Personal testing tool — NOT the official demo (that's demo.py, with fixed
test inputs). Use this to freely try any tool with your own inputs while
developing/debugging.

Run:
    python interactive.py
"""

import asyncio
from client import MeridianAgentClient

ROLE_TOKENS = {
    "1": ("Front Desk Nurse", "token_nurse_123"),
    "2": ("Attending Surgeon", "token_surg_456"),
    "3": ("Blood Bank Director", "token_dir_789"),
    "4": ("Pharmacy Tech", "token_pharm_101"),
}

TOOL_MENU = {
    "1": "get_patient_vitals",
    "2": "check_blood_inventory",
    "3": "allocate_blood",
    "4": "schedule_surgery",
    "5": "run_crossmatch_compatibility",
    "6": "generate_surgical_handoff",
    "7": "(read) Emergency Transfusion Policy resource",
    "8": "(read) draft_surgical_transfer_summary prompt",
}


def ask(prompt_text: str, cast=str):
    raw = input(f"    {prompt_text}: ").strip()
    return cast(raw)


async def choose_role() -> MeridianAgentClient:
    print("\nWho are you connecting as?")
    for key, (name, _) in ROLE_TOKENS.items():
        print(f"  {key}. {name}")
    choice = input("> ").strip()
    role_name, token = ROLE_TOKENS.get(choice, ROLE_TOKENS["2"])
    print(f"\nConnecting as {role_name}...")
    client = MeridianAgentClient(token)
    await client.connect()
    return client


async def call_get_patient_vitals(client):
    patient_id = ask("patient_id", int)
    result = await client.call_tool("get_patient_vitals", {"patient_id": patient_id})
    print(result)


async def call_check_blood_inventory(client):
    blood_type = ask("blood_type (e.g. O-, A+, AB-)")
    result = await client.call_tool("check_blood_inventory", {"blood_type": blood_type})
    print(result)


async def call_allocate_blood(client):
    inventory_id = ask("inventory_id", int)
    patient_id = ask("patient_id", int)
    authorized_by = ask("authorized_by (Staff.id)", int)
    units = ask("units", int)
    allocation_time = ask("allocation_time (YYYY-MM-DDTHH:MM:SS)")
    result = await client.call_tool(
        "allocate_blood",
        {
            "inventory_id": inventory_id,
            "patient_id": patient_id,
            "authorized_by": authorized_by,
            "units": units,
            "allocation_time": allocation_time,
        },
    )
    print(result)


async def call_schedule_surgery(client):
    patient_id = ask("patient_id", int)
    surgeon_id = ask("surgeon_id (Staff.id)", int)
    operating_room = ask("operating_room (e.g. OR-1)")
    scheduled_time = ask("scheduled_time (YYYY-MM-DDTHH:MM:SS)")
    end_time = ask("end_time (YYYY-MM-DDTHH:MM:SS)")
    result = await client.call_tool(
        "schedule_surgery",
        {
            "patient_id": patient_id,
            "surgeon_id": surgeon_id,
            "operating_room": operating_room,
            "scheduled_time": scheduled_time,
            "end_time": end_time,
        },
    )
    print(result)


async def call_run_crossmatch(client):
    patient_id = ask("patient_id", int)

    async def on_progress(progress, total, message):
        print(f"    ...progress {progress}/{total}")

    result = await client.call_tool(
        "run_crossmatch_compatibility", {"patient_id": patient_id}, progress_callback=on_progress
    )
    print(result)


async def call_generate_handoff(client):
    surgery_id = ask("surgery_id", int)
    result = await client.call_tool("generate_surgical_handoff", {"surgery_id": surgery_id})
    print(result)


async def call_read_policy(client):
    contents = await client.read_policy()
    print(contents)


async def call_get_prompt(client):
    surgery_id = ask("surgery_id")
    result = await client.get_prompt("draft_surgical_transfer_summary", {"surgery_id": surgery_id})
    print(result)


HANDLERS = {
    "1": call_get_patient_vitals,
    "2": call_check_blood_inventory,
    "3": call_allocate_blood,
    "4": call_schedule_surgery,
    "5": call_run_crossmatch,
    "6": call_generate_handoff,
    "7": call_read_policy,
    "8": call_get_prompt,
}


async def main():
    client = await choose_role()
    print("\nConnected. Type 'switch' to reconnect as a different role, 'exit' to quit.\n")

    try:
        while True:
            print("What do you want to call?")
            for key, label in TOOL_MENU.items():
                print(f"  {key}. {label}")
            print("  switch. reconnect as a different role")
            print("  exit. quit")

            choice = input("> ").strip().lower()

            if choice == "exit":
                break
            elif choice == "switch":
                await client.close()
                client = await choose_role()
                continue
            elif choice in HANDLERS:
                try:
                    await HANDLERS[choice](client)
                except Exception as e:
                    print(f"  ERROR: {e}")
            else:
                print("  Unrecognized choice, try again.")
            print()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())