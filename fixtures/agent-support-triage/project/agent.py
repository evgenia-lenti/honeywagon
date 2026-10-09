"""Support triage agent: reads the support inbox and answers customers."""

import asyncio
import base64
import json
import pickle
from pathlib import Path
from typing import Any

import requests
from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server, query, tool

SLACK_BOT_TOKEN = "xoxb-FAKE-FIXTURE-NOT-A-REAL-TOKEN"
INBOX = Path("inbox")
CUSTOMERS = Path("data/customers.json")


def text(value: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": value}]}


@tool("read_inbox", "Read the unanswered emails from customers", {})
async def read_inbox(args: dict[str, Any]) -> dict[str, Any]:
    emails = [path.read_text() for path in INBOX.glob("*.eml")]
    return text("\n\n".join(emails))


@tool("lookup_customer", "Look up a customer's orders and address", {"email": str})
async def lookup_customer(args: dict[str, Any]) -> dict[str, Any]:
    customers = json.loads(CUSTOMERS.read_text())
    return text(json.dumps(customers[args["email"]]))


@tool("post_message", "Post a message to a Slack channel", {"channel": str, "text": str})
async def post_message(args: dict[str, Any]) -> dict[str, Any]:
    requests.post(
        "https://slack.com/api/chat.postMessage",
        json={"channel": args["channel"], "text": args["text"]},
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        timeout=10,
        verify=False,
    )
    return text("sent")


@tool("restore_draft", "Restore a draft answer that was saved earlier", {"draft": str})
async def restore_draft(args: dict[str, Any]) -> dict[str, Any]:
    draft = pickle.loads(base64.b64decode(args["draft"]))
    return text(draft["body"])


support_tools = create_sdk_mcp_server(
    name="support",
    version="1.0.0",
    tools=[read_inbox, lookup_customer, post_message, restore_draft],
)

options = ClaudeAgentOptions(
    system_prompt="You are the support triage agent. Answer every email in the inbox.",
    mcp_servers={"support": support_tools},
    allowed_tools=[
        "mcp__support__read_inbox",
        "mcp__support__lookup_customer",
        "mcp__support__post_message",
        "mcp__support__restore_draft",
    ],
    permission_mode="bypassPermissions",
)


async def main() -> None:
    async for message in query(prompt="Process the support inbox.", options=options):
        print(message)


asyncio.run(main())
