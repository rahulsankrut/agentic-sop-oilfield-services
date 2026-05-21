"""Test client for the Procurement Approval Agent A2A server.

Usage:
    # Terminal 1: Start server
    poetry run python scripts/procurement_local_server.py

    # Terminal 2: Run test client
    poetry run python scripts/procurement_test_client.py
"""

import asyncio
import json
import uuid

import httpx

AGENT_URL = "http://localhost:8089"


async def test_agent():
    """Test the Procurement Approval Agent via A2A protocol."""
    print("=" * 60)
    print("Testing Procurement Approval Agent via A2A")
    print("=" * 60)
    print()

    async with httpx.AsyncClient(timeout=120.0) as http_client:
        # Fetch the agent card
        print("1. Fetching agent card...")
        card_response = await http_client.get(f"{AGENT_URL}/.well-known/agent.json")

        if card_response.status_code != 200:
            print(f"   Error: Could not fetch agent card (status {card_response.status_code})")
            print("   Make sure local_server.py is running!")
            return

        agent_card = card_response.json()
        print(f"   Agent: {agent_card.get('name')}")
        print(f"   Description: {agent_card.get('description', '')[:60]}...")
        print()

        print("2. Test: Review a sample SourcingPlan")
        print("-" * 40)
        sample_plan = (
            "SourcingPlan: Tool X-V7 from Lagos repair shop to Luanda by Friday. "
            "Transit: ground (50km, $40K). Customer: Gulf Petroleum (authorized). "
            "Equivalence: InTouch spec §3.2 (Tool X canonical). "
            "Cost: $40,000 USD. Workforce available, no blockers identified. "
            "Avoided cost: $380K vs. naive Darwin cargo charter baseline."
        )
        await send_request(http_client, sample_plan)
        print()

    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


async def send_request(client: httpx.AsyncClient, request_data: str):
    """Send a request via A2A JSON-RPC."""
    message_id = str(uuid.uuid4())

    payload = {
        "jsonrpc": "2.0",
        "id": message_id,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": message_id,
                "role": "user",
                "parts": [{"kind": "text", "text": request_data}],
            },
            "configuration": {
                "acceptedOutputModes": ["text"],
            },
        },
    }

    print("   Sending request...")

    try:
        response = await client.post(
            f"{AGENT_URL}/",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            print(f"   Error: HTTP {response.status_code}")
            print(f"   {response.text[:200]}")
            return

        result = response.json()

        if "error" in result:
            print(f"   Error: {result['error']}")
            return

        if "result" in result:
            task_result = result["result"]

            if "artifacts" in task_result:
                for artifact in task_result["artifacts"]:
                    for part in artifact.get("parts", []):
                        if part.get("kind") == "text":
                            response_text = part.get("text", "")
                            print("   Response:")
                            try:
                                parsed = json.loads(response_text)
                                print(f"   {json.dumps(parsed, indent=2)}")
                            except json.JSONDecodeError:
                                print(f"   {response_text}")
            else:
                status = task_result.get("status", {})
                state = status.get("state", "unknown")
                print(f"   Task state: {state}")

    except httpx.ConnectError:
        print("   Error: Could not connect to server")
        print("   Make sure local_server.py is running!")
    except Exception as e:
        print(f"   Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_agent())
