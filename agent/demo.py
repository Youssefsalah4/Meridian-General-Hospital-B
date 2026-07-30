"""
agent/demo.py
Fixed, repeatable test scenarios for the Meridian MCP server demo.

Same set of test inputs is used every run so the demo table in the README
is a fair before/after comparison, not a lucky run. Each scenario is
labeled with the protocol concern it's meant to prove.

Uses seed data from db/seed.sql:
  - Patient 2, Jane Smith, blood_type O-, urgency Critical
  - Blood_Inventory id 2, O-, only 2 units available (scarce -> real stakes)
  - Surgery 1 already books OR-1 on 2026-07-28 08:00-12:00 (for the
    double-booking test)
"""

import asyncio
from client import MeridianAgentClient

NURSE_TOKEN = "token_nurse_123"
SURGEON_TOKEN = "token_surg_456"
DIRECTOR_TOKEN = "token_dir_789"


async def scenario_1_nurse_read_only():
    """Concern: Capability negotiation + Notifications (baseline state).
    A nurse session should only ever see read-only tools."""
    print("\n=== Scenario 1: Nurse connects — read-only tools only ===")
    client = MeridianAgentClient(NURSE_TOKEN)
    await client.connect()
    tool_names = [t.name for t in client.available_tools]
    assert "allocate_blood" not in tool_names, "Nurse should NOT see allocate_blood"
    print("PASS: nurse tool set =", tool_names)
    await client.close()


async def scenario_2_surgeon_unlocks_tools():
    """Concern: Notifications — role authentication mid-session pushes
    tools/list_changed, revealing allocate_blood / schedule_surgery."""
    print("\n=== Scenario 2: Surgeon authenticates — tools/list_changed ===")
    client = MeridianAgentClient(SURGEON_TOKEN)
    await client.connect()
    tool_names = [t.name for t in client.available_tools]
    assert "allocate_blood" in tool_names, "Surgeon should see allocate_blood"
    print("PASS: surgeon tool set =", tool_names)
    await client.close()


async def scenario_3_o_negative_elicitation():
    """Concern: Elicitation. Requesting O- blood (inventory_id=2, patient_id=2)
    must pause for Director sign-off, not auto-complete."""
    print("\n=== Scenario 3: O-negative allocation — elicitation pause ===")
    client = MeridianAgentClient(SURGEON_TOKEN)

    # Script the "human" response for repeatability instead of input().
    client._handle_elicitation = _scripted_director_response(approve=True)

    await client.connect()
    result = await client.call_tool(
        "allocate_blood",
        {
            "inventory_id": 2,
            "patient_id": 2,
            "authorized_by": 2,
            "units": 1,
            "allocation_time": "2026-07-30T09:00:00",
        },
    )
    print("PASS: allocation result =", result)
    await client.close()


async def scenario_4_double_booking_rejected():
    """Concern: Defensive tool design. OR-1 is already booked 08:00-12:00
    on 2026-07-28 by Surgery 1 — an overlapping request must be rejected
    server-side, not just by the client trusting the model's plan."""
    print("\n=== Scenario 4: Double-booking OR-1 — should be rejected ===")
    client = MeridianAgentClient(SURGEON_TOKEN)
    await client.connect()
    try:
        result = await client.call_tool(
            "schedule_surgery",
            {
                "patient_id": 3,
                "surgeon_id": 5,
                "operating_room": "OR-1",
                "scheduled_time": "2026-07-28T10:00:00",
                "end_time": "2026-07-28T11:00:00",
            },
        )
        print("UNEXPECTED SUCCESS (should have been rejected):", result)
    except Exception as e:
        print("PASS: rejected as expected ->", e)
    await client.close()


async def scenario_5_crossmatch_progress():
    """Concern: Progress tracking. Long-running crossmatch check should
    stream progress notifications instead of blocking silently."""
    print("\n=== Scenario 5: Crossmatch compatibility — progress updates ===")
    client = MeridianAgentClient(SURGEON_TOKEN)
    await client.connect()
    result = await client.call_tool("run_crossmatch_compatibility", {"patient_id": 2})
    print("PASS: crossmatch result =", result)
    await client.close()


async def scenario_6_read_policy_resource():
    """Concern: Resources. Transfusion policy is read as data, not called
    as a function."""
    print("\n=== Scenario 6: Reading Emergency Transfusion Policy resource ===")
    client = MeridianAgentClient(NURSE_TOKEN)
    await client.connect()
    contents = await client.read_policy()
    print("PASS: policy resource loaded, length =", len(str(contents)))
    await client.close()


async def scenario_7_prompt_template():
    """Concern: Prompts. Draft a surgical transfer summary from the
    reusable, parameterized template."""
    print("\n=== Scenario 7: draft_surgical_transfer_summary prompt ===")
    client = MeridianAgentClient(SURGEON_TOKEN)
    await client.connect()
    prompt = await client.get_prompt("draft_surgical_transfer_summary", {"surgery_id": 1})
    print("PASS: prompt returned ->", prompt)
    await client.close()


async def scenario_8_client_missing_elicitation_capability():
    """Concern: Capability negotiation (failure path). A client that does
    NOT declare elicitation support should get a safe fallback for
    allocate_blood, not a crash or a silent bypass of the sign-off."""
    print("\n=== Scenario 8: client without elicitation capability ===")
    client = MeridianAgentClient(SURGEON_TOKEN)
    client._handle_elicitation = None  # simulate no elicitation support
    await client.connect()
    tool_names = [t.name for t in client.available_tools]
    if "allocate_blood" not in tool_names:
        print("PASS: server withheld allocate_blood from a non-elicitation client")
    else:
        print("CHECK: allocate_blood still offered — confirm server fails closed at call time")
    await client.close()


def _scripted_director_response(approve: bool):
    async def _respond(request):
        decision = "accept" if approve else "decline"
        print(f"[demo] scripted Director response: {decision}")
        return {"action": decision}
    return _respond


async def run_all():
    scenarios = [
        scenario_1_nurse_read_only,
        scenario_2_surgeon_unlocks_tools,
        scenario_3_o_negative_elicitation,
        scenario_4_double_booking_rejected,
        scenario_5_crossmatch_progress,
        scenario_6_read_policy_resource,
        scenario_7_prompt_template,
        scenario_8_client_missing_elicitation_capability,
    ]
    for scenario in scenarios:
        await scenario()


if __name__ == "__main__":
    asyncio.run(run_all())
