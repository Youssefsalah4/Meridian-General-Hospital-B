"""
agent/client.py
Meridian Surgical & Blood Bank — Agent Client

Built against mcp_server/TOOLS_SPEC.md. Tool names / schemas here should be
kept in sync with Person 2's actual server. Swap the connection block in
`connect()` from stdio -> Streamable HTTP once the server moves to remote,
per the lab's transport requirement.

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

# from mcp.client.streamable_http import streamablehttp_client  # for remote transport later

load_dotenv()

# --- Config -----------------------------------------------------------
TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")  # "stdio" | "http"
SERVER_SCRIPT = os.getenv("MCP_SERVER_SCRIPT", "../mcp_server/server.py")
SERVER_HTTP_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")


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
            params = StdioServerParameters(command="python", args=[SERVER_SCRIPT])
            read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        else:
            # read, write, _ = await self._exit_stack.enter_async_context(
            #     streamablehttp_client(SERVER_HTTP_URL, headers={"Authorization": self.staff_auth_token})
            # )
            raise NotImplementedError("Wire up streamable_http_client once server supports remote transport.")

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

        await self._refresh_tools()
        print(f"[client] connected. tools visible: {[t.name for t in self.available_tools]}")

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
    async def _handle_elicitation(self, request):
        """
        Called by the SDK when the server sends elicitation/create — e.g.
        allocate_blood requesting O-negative units needs Director sign-off.

        In the real demo this should prompt a human (or a scripted director
        response for repeatable test runs — see agent/demo.py). It must NOT
        silently auto-approve.
        """
        print(f"[client] ELICITATION requested: {request.message}")
        for field, schema in request.requestedSchema.get("properties", {}).items():
            print(f"    needs: {field} ({schema.get('description', '')})")

        # Placeholder — demo.py overrides this with scripted director responses
        # for repeatable test runs. A real interactive session would prompt input().
        decision = input("[client] Director decision (approve/deny): ").strip().lower()
        return {"action": "accept" if decision == "approve" else "decline"}

    # ------------------------------------------------------------------
    # Sampling: server asks OUR model to reason (e.g. urgency vs. policy)
    # ------------------------------------------------------------------
    async def _handle_sampling(self, request):
        """
        Server-initiated sampling/createMessage. The server does not use its
        own model here — it borrows the client's, so cost/latency shows up
        on our side. Wire this to whichever model the team picked.
        """
        raise NotImplementedError(
            "Wire this to your chosen model provider (Claude/GPT/Gemini/etc). "
            "Should send request.messages to the model and return its reply "
            "in the shape the SDK expects."
        )

    # ------------------------------------------------------------------
    # Resources: fetched as data, not called as a function
    # ------------------------------------------------------------------
    async def read_policy(self, uri: str = "resource://policy/emergency-transfusion"):
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
    async def call_tool(self, name: str, arguments: dict):
        if name not in [t.name for t in self.available_tools]:
            raise PermissionError(
                f"'{name}' is not in this session's visible tool set "
                f"(role/auth may not permit it yet)."
            )
        return await self.session.call_tool(name, arguments)

    async def close(self):
        await self._exit_stack.aclose()


async def _smoke_test():
    """Minimal manual check once server.py exists. Not the real demo."""
    client = MeridianAgentClient(staff_auth_token=os.getenv("STAFF_TOKEN", "token_nurse_123"))
    try:
        await client.connect()
        vitals = await client.call_tool("get_patient_vitals", {"patient_id": 2})
        print(vitals)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(_smoke_test())