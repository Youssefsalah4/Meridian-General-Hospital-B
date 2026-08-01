"""
agent/interactive.py

"""

import asyncio
import os
from client import MeridianAgentClient


TOOL_DISPLAY_NAMES = {
    "get_patient_vitals": "Get Patient Vitals",
    "check_blood_inventory": "Check Blood Inventory",
    "allocate_blood": "Authorize Blood Allocation",
    "schedule_surgery": "Schedule Surgery Case",
    "run_crossmatch_compatibility": "Run Crossmatch Compatibility",
    "generate_surgical_handoff": "Generate Surgical Handoff (AI Sampling)",
}

def ask(prompt_text: str, cast=str):
    raw = input(f"    {prompt_text}: ").strip()
    return cast(raw)

async def login_screen() -> MeridianAgentClient:
    """شاشة تسجيل الدخول بواسطة التوكن"""
    print("\n" + "="*45)
    print("      MERIDIAN HOSPITAL - SECURE LOGIN")
    print("="*45)
    print("Please enter your staff authentication token.")
    print("Example: token_nurse_123 or token_surg_456")
    
    token = input("\nAuth Token > ").strip()
    
    if not token:
        print("Error: Token is required to access the system.")
        return await login_screen()

    print(f"\n[system] Authenticating and starting MCP session...")
    client = MeridianAgentClient(token)
    try:
        await client.connect()
        return client
    except Exception as e:
        print(f"\n[!] Connection Failed: {e}")
        print("Please check if the server is running and the token is valid.")
        return await login_screen()

# --- Handlers for Tools ---
async def call_get_patient_vitals(client):
    patient_id = ask("patient_id", int)
    result = await client.call_tool("get_patient_vitals", {"patient_id": patient_id})
    print(result)

async def call_check_blood_inventory(client):
    blood_type = ask("blood_type (e.g. O-, A+)")
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
        print(f"    ... Progress: {progress}/{total}%")
    
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
    print("\n--- Emergency Transfusion Policy ---")
    print(contents[0].text if contents else "No content available.")

async def call_get_prompt(client):
    surgery_id = ask("surgery_id")
    result = await client.get_prompt("draft_surgical_transfer_summary", {"surgery_id": surgery_id})
    print(result)

# ربط أسماء الأدوات بالدوال
HANDLERS = {
    "get_patient_vitals": call_get_patient_vitals,
    "check_blood_inventory": call_check_blood_inventory,
    "allocate_blood": call_allocate_blood,
    "schedule_surgery": call_schedule_surgery,
    "run_crossmatch_compatibility": call_run_crossmatch,
    "generate_surgical_handoff": call_generate_handoff,
}

async def main():
    client = await login_screen()
    
    try:
        while True:
            # الحصول على الأدوات التي سمح بها السيرفر لهذا المستخدم فقط
            available_tools = [t.name for t in client.available_tools]
            
            print("\n" + "-"*30)
            print("  AVAILABLE ACTIONS")
            print("-"*30)
            
            menu_map = {}
            counter = 1
            
            # عرض الأدوات المسموحة فقط
            for tool_name in available_tools:
                if tool_name in HANDLERS:
                    display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
                    print(f"  {counter}. {display_name}")
                    menu_map[str(counter)] = tool_name
                    counter += 1
            
            # إضافة الموارد والمطالبات (Resources & Prompts)
            res_idx = counter
            prompt_idx = counter + 1
            print(f"  {res_idx}. (Resource) View Emergency Policy")
            print(f"  {prompt_idx}. (Prompt) Draft Transfer Summary Template")
            
            print("\n  switch. Reconnect as different user")
            print("  exit.   Quit")

            choice = input("\nAction > ").strip().lower()

            if choice == "exit":
                break
            elif choice == "switch":
                await client.close()
                client = await login_screen()
                continue
            elif choice == str(res_idx):
                await call_read_policy(client)
            elif choice == str(prompt_idx):
                await call_get_prompt(client)
            elif choice in menu_map:
                tool_to_call = menu_map[choice]
                try:
                    await HANDLERS[tool_to_call](client)
                except Exception as e:
                    print(f"  [!] Error: {e}")
            else:
                print("  [!] Invalid choice, please try again.")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
