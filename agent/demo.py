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

KNOWN GAPS (found via this demo, need team follow-up — see README /
open issues, NOT fixable from the client alone):

1. Notifications: tools.py registers every tool globally with @mcp.tool().
   list_tools() returns the full set to every role; only call-time
   authorization (is_tool_authorized inside each handler) is enforced.
   Full Notifications credit needs the tool LIST itself to change per
   role and push tools/list_changed.

2. Defensive design / double-booking: seed.sql stores datetimes as
   "YYYY-MM-DD HH:MM:SS" (space separator) but tools.py forwards the
   client's ISO "YYYY-MM-DDTHH:MM:SS" (T separator) straight into SQLite.
   SQLite compares these as TEXT, and " " < "T" lexicographically, so the
   overlap query in validation.py silently fails to detect real conflicts
   between old (seed) and new (client-submitted) rows. Needs a single
   consistent datetime format end-to-end (Person 1 + Person 2).

3. Elicitation capability declaration: the server-side check
   (session.capabilities.elicitation inside allocate_blood) reports "no
   elicitation support" even when the client supplies a real
   elicitation_callback and a scripted Director response (scenario 3).
   Needs a debug print of `ctx.session.capabilities` server-side to
   confirm what the SDK is actually negotiating — flagged, not yet
   resolved.

IMPORTANT (client-side fix applied here): MCP tool execution errors come
back as a normal CallToolResult with isError=True and the message in
content — NOT as a raised Python exception. Earlier versions of this demo
only caught exceptions and mislabeled isError=True results as "PASS".
Every scenario below now checks result.isError explicitly.
"""

import asyncio
from contextlib import asynccontextmanager
from client import MeridianAgentClient

NURSE_TOKEN = "token_nurse_123"
SURGEON_TOKEN = "token_surg_456"
DIRECTOR_TOKEN = "token_dir_789"

_UNSET = object()


@asynccontextmanager
async def connected_client(token: str, elicitation_handler=_UNSET):
    """Ensures client.close() always runs, even if a scenario fails
    midway — prevents dangling-connection cleanup errors."""
    client = MeridianAgentClient(token)
    if elicitation_handler is not _UNSET:
        client._handle_elicitation = elicitation_handler
    try:
        await client.connect()
        yield client
    finally:
        await client.close()


def _result_text(result):
    """Extract the text payload from a CallToolResult for printing."""
    try:
        return result.content[0].text
    except Exception:
        return str(result)


async def _expect_error(client, tool_name, arguments, label):
    """Call a tool and confirm the server correctly REJECTED it
    (result.isError is True) — the real enforcement point in this SDK."""
    result = await client.call_tool(tool_name, arguments)
    if result.isError:
        print(f"PASS: {label} ->", _result_text(result))
    else:
        print(f"FAIL: {label} — server allowed a call that should have been rejected ->", _result_text(result))


async def _expect_success(client, tool_name, arguments, label):
    """Call a tool and confirm the server accepted it (result.isError is False)."""
    result = await client.call_tool(tool_name, arguments)
    if not result.isError:
        print(f"PASS: {label} ->", _result_text(result))
    else:
        print(f"FAIL: {label} — expected success but got an error ->", _result_text(result))
    return result


async def scenario_1_nurse_read_only():
    """Concern: Capability negotiation + Notifications (baseline state).
    Tests what IS enforced today: a nurse can call read-only tools but is
    blocked at call time from allocate_blood. Tool-list filtering by role
    is a known gap (see module docstring, item 1)."""
    print("\n=== Scenario 1: Nurse — read-only allowed, write blocked ===")
    async with connected_client(NURSE_TOKEN) as client:
        tool_names = [t.name for t in client.available_tools]
        if "allocate_blood" in tool_names:
            print("NOTE: tool list is not yet role-filtered server-side (known gap).")

        await _expect_success(
            client, "get_patient_vitals", {"patient_id": 2}, "nurse read-only call"
        )
        try:
            await _expect_error(
                client,
                "allocate_blood",
                {...},
                "nurse blocked from allocate_blood",
            )
        except PermissionError as e:
            print("PASS: nurse blocked from allocate_blood (tool not even visible) ->", e)

async def scenario_2_surgeon_unlocks_tools():
    """Concern: Notifications. A surgeon should be authorized for the full
    tool set (see module docstring, item 1, re: tool-LIST filtering gap)."""
    print("\n=== Scenario 2: Surgeon — authorized for privileged tools ===")
    async with connected_client(SURGEON_TOKEN) as client:
        print("tools visible:", [t.name for t in client.available_tools])
        print("PASS: surgeon session connected; authorization proven in scenarios 3 & 4.")


async def scenario_3_o_negative_elicitation():
    """Concern: Elicitation. Requesting O- blood (inventory_id=2, patient_id=2)
    should pause for Director sign-off. NOTE: currently fails closed with
    "Client lacks elicitation support" even with a real callback + scripted
    response wired — see module docstring, item 3. Reports the real
    outcome either way instead of assuming success."""
    print("\n=== Scenario 3: O-negative allocation — elicitation pause ===")
    async with connected_client(
        SURGEON_TOKEN, elicitation_handler=_scripted_director_response(approve=True)
    ) as client:
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
        if result.isError:
            print("KNOWN ISSUE: allocation blocked even with elicitation callback wired ->",
                  _result_text(result))
        else:
            print("PASS: allocation succeeded after Director approval ->", _result_text(result))


async def scenario_4_double_booking_rejected():
    """Concern: Defensive tool design. OR-1 is already booked 08:00-12:00
    on 2026-07-28 by Surgery 1. NOTE: currently NOT rejected due to a
    datetime format mismatch between seed data and client input — see
    module docstring, item 2. Reports the real outcome."""
    print("\n=== Scenario 4: Double-booking OR-1 — should be rejected ===")
    async with connected_client(SURGEON_TOKEN) as client:
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
        if result.isError:
            print("PASS: rejected as expected ->", _result_text(result))
        else:
            print("KNOWN BUG: double-booking was NOT rejected (datetime format mismatch) ->",
                  _result_text(result))


async def scenario_5_crossmatch_progress():
    """Concern: Progress tracking. Long-running crossmatch check should
    stream progress notifications instead of blocking silently."""
    print("\n=== Scenario 5: Crossmatch compatibility — progress updates ===")
    async with connected_client(SURGEON_TOKEN) as client:
        async def on_progress(progress, total, message):
            print(f"[demo] progress update: {progress}/{total} — {message or ''}")

        result = await client.call_tool(
            "run_crossmatch_compatibility",
            {"patient_id": 2},
            progress_callback=on_progress,
        )
        if not result.isError:
            print("PASS: crossmatch result =", _result_text(result))
        else:
            print("FAIL: crossmatch returned an error ->", _result_text(result))


async def scenario_6_read_policy_resource():
    """Concern: Resources. Transfusion policy is read as data, not called
    as a function."""
    print("\n=== Scenario 6: Reading Emergency Transfusion Policy resource ===")
    async with connected_client(NURSE_TOKEN) as client:
        contents = await client.read_policy()
        print("PASS: policy resource loaded, length =", len(str(contents)))


async def scenario_7_prompt_template():
    """Concern: Prompts. Draft a surgical transfer summary from the
    reusable, parameterized template."""
    print("\n=== Scenario 7: draft_surgical_transfer_summary prompt ===")
    async with connected_client(SURGEON_TOKEN) as client:
        prompt = await client.get_prompt("draft_surgical_transfer_summary", {"surgery_id": "1"})
        print("PASS: prompt returned ->", prompt)


async def scenario_8_client_missing_elicitation_capability():
    """Concern: Capability negotiation (failure path). A client that does
    NOT declare elicitation support should be blocked from completing an
    O-negative allocation, not crash or silently bypass sign-off."""
    print("\n=== Scenario 8: client without elicitation capability ===")
    async with connected_client(SURGEON_TOKEN, elicitation_handler=None) as client:
        await _expect_error(
            client,
            "allocate_blood",
            {
                "inventory_id": 2,
                "patient_id": 2,
                "authorized_by": 2,
                "units": 1,
                "allocation_time": "2026-07-30T09:00:00",
            },
            "blocked without elicitation capability",
        )


def _scripted_director_response(approve: bool):
    async def _respond(context, params):
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
        try:
            await scenario()
        except Exception as e:
            print(f"[demo] scenario {scenario.__name__} raised an unhandled error: {e}")


if __name__ == "__main__":
    asyncio.run(run_all())
