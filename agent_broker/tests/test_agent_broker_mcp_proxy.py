"""Tests for the broker MCP proxy service and proxy app routes."""

import pytest

from opamp_broker.mcp.proxy import (
    HEADER_MCP_SESSION_ID,
    MCPProxyService,
    create_mcp_proxy_app,
)
from opamp_broker.social_collaboration.factory import create_social_collaboration_adapter


class FakeMCPClient:
    instances = []

    def __init__(
        self,
        mcp_url: str,
        timeout_seconds: int = 30,
        *,
        connection_mode: str = "auto",
        protocol_version_attempts: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        self.mcp_url = mcp_url
        self.timeout_seconds = timeout_seconds
        self.connection_mode = connection_mode
        self.protocol_version_attempts = tuple(protocol_version_attempts or ())
        self.initialize_calls: list[dict] = []
        self.tool_calls: list[tuple[str, dict]] = []
        self.closed = False
        FakeMCPClient.instances.append(self)

    async def initialize(
        self,
        *,
        protocol_version: str | None = None,
        client_info: dict | None = None,
        capabilities: dict | None = None,
    ) -> dict:
        self.initialize_calls.append(
            {
                "protocol_version": protocol_version,
                "client_info": client_info,
                "capabilities": capabilities,
            }
        )
        return {
            "protocolVersion": "2025-06-18",
            "serverInfo": {"name": "fake-upstream", "version": "1.0.0"},
            "capabilities": {},
        }

    async def list_tools(self) -> dict:
        return {
            "tools": [
                {
                    "name": "ping",
                    "description": "Ping test tool",
                    "inputSchema": {"type": "object"},
                }
            ]
        }

    async def call_tool(self, name: str, arguments: dict) -> dict:
        self.tool_calls.append((name, arguments))
        return {"content": [{"type": "text", "text": f"{name}:{arguments}"}]}

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_mcp_proxy_initialize_list_and_call_round_trip() -> None:
    """Verifies the proxy can initialize a session, list tools, and call a tool."""
    FakeMCPClient.instances.clear()
    service = MCPProxyService(
        mcp_url="http://provider.example/mcp",
        timeout_seconds=30,
        connection_mode="json",
        protocol_version_attempts=("2025-06-18", "2025-03-26"),
        client_factory=FakeMCPClient,
    )
    app = create_mcp_proxy_app(proxy_service=service, mcp_path="/mcp")
    client = app.test_client()

    initialize_response = await client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "clientInfo": {"name": "claude-ai", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            },
        },
    )

    assert initialize_response.status_code == 200
    initialize_payload = await initialize_response.get_json()
    broker_session_id = initialize_response.headers.get(HEADER_MCP_SESSION_ID)
    assert broker_session_id
    assert initialize_payload["result"]["protocolVersion"] == "2025-06-18"
    assert FakeMCPClient.instances[0].initialize_calls[0]["protocol_version"] == "2025-11-25"

    list_response = await client.post(
        "/mcp",
        headers={HEADER_MCP_SESSION_ID: broker_session_id},
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert list_response.status_code == 200
    list_payload = await list_response.get_json()
    assert list_payload["result"]["tools"][0]["name"] == "ping"

    call_response = await client.post(
        "/mcp",
        headers={HEADER_MCP_SESSION_ID: broker_session_id},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "ping", "arguments": {"value": "ok"}},
        },
    )
    assert call_response.status_code == 200
    call_payload = await call_response.get_json()
    assert "ping" in call_payload["result"]["content"][0]["text"]
    assert FakeMCPClient.instances[0].tool_calls == [("ping", {"value": "ok"})]

    await service.close()
    assert FakeMCPClient.instances[0].closed is True


@pytest.mark.asyncio
async def test_mcp_proxy_requires_session_for_stateful_methods() -> None:
    """Verifies stateful MCP methods are rejected until a session is initialized."""
    service = MCPProxyService(
        mcp_url="http://provider.example/mcp",
        timeout_seconds=30,
        connection_mode="json",
        protocol_version_attempts=("2025-06-18",),
        client_factory=FakeMCPClient,
    )
    app = create_mcp_proxy_app(proxy_service=service)
    client = app.test_client()

    response = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload["error"]["message"] == "an active MCP session is required"


def test_social_collaboration_factory_supports_none() -> None:
    """Verifies the social collaboration factory exposes the noop adapter."""
    adapter = create_social_collaboration_adapter("none")
    assert adapter.__class__.__name__ == "NoopSocialCollaborationAdapter"
