"""
agent/client.py
Meridian Surgical & Blood Bank — Agent Client

Wired against the real mcp_server/ implementation (Task 2, complete).

Covers, on the client side, every protocol concern the server implements:
  - capability negotiation  -> _check_capabilities()
  - notifications           -> _on_tools_list_changed()
  - elicitation              -> _handle_elicitation()
  - resources                -> read_policy()
  - prompts                  -> get_prompt()
  - sampling                 -> _handle_sampling()  (server calls back into US)
  - progress tracking        -> _on_progress()
"""

import asyncio
import os
from contextlib import AsyncExitStack
from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client  # server.py runs "sse" transport in production

load_dotenv()

# --- Config -----------------------------------------------------------
TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")  # "stdio" | "sse"  (matches mcp_server/transport.py)
SERVER_SCRIPT = os.getenv("MCP_SERVER_SCRIPT", "../mcp_server/server.py")
SERVER_SSE_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/sse")


class MeridianAgentClient:
    """Wraps an MCP ClientSession with the behaviors this lab grades on."""

    def __init__(self, staff_auth_token: str):
        self.staff_auth_token = staff_auth_token
        self.session: ClientSession | None = None
        self.server_capabilities = {}
        self.available_tools = []
        self._exit_stack = AsyncExitStack()

    # ------------------------------------------------------------------
    # Connection + capability negotiation
    # ------------------------------------------------------------------
    async def connect(self):
        if TRANSPORT == "stdio":
            # FIX 1: the server reads its role from the STAFF_TOKEN env var of
            # its OWN process (see mcp_server/tools.py _get_current_token()).
            # Since stdio spawns the server as a child process, we MUST pass
            # our token into that child's environment or the server will
            # always fall back to the nurse default, no matter who we are.
            child_env = os.environ.copy()
            child_env["STAFF_TOKEN"] = self.staff_auth_token

            params = StdioServerParameters(
                command="python",
                args=[SERVER_SCRIPT],
                env=child_env,
            )
            read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        elif TRANSPORT == "sse":
            
            read, write = await self._exit_stack.enter_async_context(sse_client(SERVER_SSE_URL))
        else:
            raise ValueError(f"Unknown MCP_TRANSPORT '{TRANSPORT}' — expected 'stdio' or 'sse'.")

        self.session = await self._exit_stack.enter_async_context(
            ClientSession(
                read,
                write,
                elicitation_callback=self._handle_elicitation,
                sampling_callback=self._handle_sampling,
                message_handler=self._handle_server_message,
            )
        )

        init_result = await self.session.initialize()
        self.server_capabilities = init_result.capabilities

        # Don't assume the server supports elicitation: check before relying
        # on any tool that depends on it (allocate_blood does for O-negative).
        if not getattr(self.server_capabilities, "elicitation", None):
            print("[client] WARNING: server did not declare elicitation support. "
                  "allocate_blood may fail closed for O- requests, or the tool "
                  "may not even be offered.")

        
        if not getattr(self.server_capabilities, "resources", None):
            print("[client] NOTE: server did not declare resources support. "
                  "read_policy() will not be called.")

        await self._refresh_tools()
        print(f"[client] connected as role-token={self.staff_auth_token!r}. "
              f"tools visible: {[t.name for t in self.available_tools]}")

    async def _refresh_tools(self):
        result = await self.session.list_tools()
        self.available_tools = result.tools

    # ------------------------------------------------------------------
    # Notifications: role change -> tools/list_changed -> re-list, don't poll
    # ------------------------------------------------------------------
    async def _handle_server_message(self, message):
        """Generic message handler. MCP SDK routes notifications here."""
        method = getattr(message, "method", None)
        if method == "notifications/tools/list_changed":
            print("[client] received tools/list_changed — refreshing tool set")
            await self._refresh_tools()
        elif method == "notifications/progress":
            self._on_progress(message)

    def _on_progress(self, message):
        params = getattr(message, "params", {})
        pct = params.get("progress")
        total = params.get("total")
        print(f"[client] progress: {pct}/{total}")

    # ------------------------------------------------------------------
    # Elicitation: pause and get a real human decision (Blood Bank Director)
    # ------------------------------------------------------------------
    async def _handle_elicitation(self, context, params):
        """
        Called by the SDK when the server sends elicitation/create — e.g.
        allocate_blood requesting O-negative units needs Director sign-off.
        The SDK calls this with (context, params) — context carries
        request metadata, params is the actual ElicitRequestParams.
        """
        print(f"[client] ELICITATION requested: {params.message}")
        for field, schema in params.requestedSchema.get("properties", {}).items():
            print(f"    needs: {field} ({schema.get('description', '')})")

        decision = input("[client] Director decision (approve/deny): ").strip().lower()
        return {"action": "accept" if decision == "approve" else "decline"}

    # ------------------------------------------------------------------
    # Sampling: server asks OUR model to reason (e.g. urgency vs. policy)
    # ------------------------------------------------------------------
    async def _handle_sampling(self, request):
        """
        Server-initiated sampling/createMessage. NOTE: as of this Task 2
        build, no tool in mcp_server/tools.py actually calls
        session.send_request("sampling/createMessage", ...) yet — this
        callback is registered and ready, but will not fire until Person 2
        wires a tool to use it. Kept as a graceful fallback (not a crash)
        so the demo doesn't break if/when that lands mid-integration.
        """
        print("[client] SAMPLING requested by server — no model wired yet.")
        return {
            "role": "assistant",
            "content": {
                "type": "text",
                "text": "[client] sampling_callback not yet wired to a model provider.",
            },
        }

    # ------------------------------------------------------------------
    # Resources: fetched as data, not called as a function
    # ------------------------------------------------------------------
    async def read_policy(self, uri: str = "resource://policy/emergency-transfusion"):
        if not getattr(self.server_capabilities, "resources", None):
            print("[client] Skipping read_policy — server has no resources capability.")
            return None
        result = await self.session.read_resource(uri)
        return result.contents

    # ------------------------------------------------------------------
    # Prompts: canned, parameterized starting point
    # ------------------------------------------------------------------
    async def get_prompt(self, name: str, arguments: dict):
        return await self.session.get_prompt(name, arguments)

    # ------------------------------------------------------------------
    # Tool calls
    # ------------------------------------------------------------------
    async def call_tool(self, name: str, arguments: dict, progress_callback=None):
        if name not in [t.name for t in self.available_tools]:
            raise PermissionError(
                f"'{name}' is not in this session's visible tool set "
                f"(role/auth may not permit it yet)."
            )
        if progress_callback:
            return await self.session.call_tool(name, arguments, progress_callback=progress_callback)
        return await self.session.call_tool(name, arguments)

    async def close(self):
        await self._exit_stack.aclose()


async def _smoke_test():
    """Minimal manual check against the real server."""
    client = MeridianAgentClient(staff_auth_token=os.getenv("STAFF_TOKEN", "token_nurse_123"))
    try:
        await client.connect()
        vitals = await client.call_tool("get_patient_vitals", {"patient_id": 2})
        print(vitals)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(_smoke_test())
