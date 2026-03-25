#!/usr/bin/env python3
"""Conversational Jira story creator UI powered by Claude."""

import os
import time
from base64 import b64encode
from typing import Generator

import gradio as gr
import requests
import anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

JIRA_URL = os.environ["JIRA_URL"].rstrip("/")
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY = os.environ["JIRA_PROJECT_KEY"]


def _jira_auth() -> str:
    return "Basic " + b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()


def _adf_doc(description: str, acceptance_criteria: list[str]) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": description}]},
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Acceptance Criteria"}],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": item}]}
                        ],
                    }
                    for item in acceptance_criteria
                ],
            },
        ],
    }


def _create_jira_issue(
    summary: str,
    issue_type: str,
    description: str,
    acceptance_criteria: list[str],
    labels: list[str],
) -> str:
    r = requests.post(
        f"{JIRA_URL}/rest/api/3/issue",
        json={
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": summary,
                "description": _adf_doc(description, acceptance_criteria),
                "issuetype": {"name": issue_type},
                "labels": labels,
            }
        },
        headers={
            "Authorization": _jira_auth(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["key"]


TOOLS = [
    {
        "name": "create_jira_issue",
        "description": (
            f"Create a single Jira issue in the {JIRA_PROJECT_KEY} project. "
            "Always prefix the summary with the appropriate tag: "
            "[mobile app], [client portal], [Admin portal], [STRUCTURAL], or [DESIGN]. "
            "For bugs, prepend [Bug] before the portal tag. "
            "Use Story for features/improvements, Task for bugs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": (
                        "Issue title with prefix tags, "
                        "e.g. '[Bug] [mobile app] Login button broken'"
                    ),
                },
                "issue_type": {
                    "type": "string",
                    "enum": ["Story", "Task"],
                    "description": "Story for features, Task for bugs",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed context and problem statement",
                },
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific, testable acceptance criteria (3-6 bullets)",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Labels e.g. ['mobile', 'olympus'] "
                        "or ['client-portal', 'olympus', 'bug']"
                    ),
                },
            },
            "required": [
                "summary",
                "issue_type",
                "description",
                "acceptance_criteria",
                "labels",
            ],
        },
    }
]

SYSTEM_PROMPT = f"""You are a Jira story creation assistant for the Olympus/Gyglers platform (project: {JIRA_PROJECT_KEY}).

When the user describes work items, parse each one into a structured Jira issue and create it using the create_jira_issue tool. Handle multiple items in a single message.

Title prefix rules (always apply one):
- [mobile app]    — Gygler mobile app (Angular + Capacitor)
- [client portal] — client-facing web portal
- [Admin portal]  — internal admin portal
- [STRUCTURAL]    — backend / architectural / infrastructure work
- [DESIGN]        — UI/UX polish

Bug rule: prepend [Bug] before the portal tag, e.g. "[Bug] [mobile app] ..."

Issue type:
- Story — features, improvements, new functionality
- Task  — bugs (always add [Bug] prefix to summary too)

After creating all issues, give a concise summary table:
| Key | Title | Type |
listing every created issue."""

anthropic_client = anthropic.Anthropic()


def respond(message: str, history: list) -> Generator[str, None, None]:
    """Stream Claude's response and execute Jira tool calls as they arrive."""
    messages = []
    for turn in history:
        # Gradio passes history as list of dicts in messages format
        if isinstance(turn, dict):
            messages.append({"role": turn["role"], "content": turn["content"]})
        else:
            # Fallback: old-style list-of-lists
            user_msg, assistant_msg = turn
            messages.append({"role": "user", "content": user_msg})
            if assistant_msg:
                messages.append({"role": "assistant", "content": assistant_msg})

    messages.append({"role": "user", "content": message})

    accumulated = ""

    while True:
        with anthropic_client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                accumulated += text
                yield accumulated

            response = stream.get_final_message()

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type != "tool_use" or block.name != "create_jira_issue":
                    continue

                inp = block.input
                accumulated += f"\n\n> Creating `{inp['summary']}`..."
                yield accumulated

                try:
                    key = _create_jira_issue(
                        summary=inp["summary"],
                        issue_type=inp["issue_type"],
                        description=inp["description"],
                        acceptance_criteria=inp["acceptance_criteria"],
                        labels=inp["labels"],
                    )
                    time.sleep(0.15)
                    result = f"Created {key}: {inp['summary']}"
                    accumulated += f" **[{key}]**"
                except requests.HTTPError as exc:
                    error = exc.response.text if exc.response else str(exc)
                    result = f"Failed: {error}"
                    accumulated += f" FAILED — {error}"
                except Exception as exc:
                    result = f"Failed: {exc}"
                    accumulated += f" FAILED — {exc}"

                yield accumulated

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

        else:
            break


demo = gr.ChatInterface(
    fn=respond,
    title="Jira Story Creator — Olympus/Gyglers",
    description=(
        f"Describe backlog items in plain English and I'll create them in Jira.  \n"
        f"**Project:** `{JIRA_PROJECT_KEY}` &nbsp;|&nbsp; **Board:** {JIRA_URL}/jira/software/projects/{JIRA_PROJECT_KEY}/boards"
    ),
    examples=[
        "Add a bug: the apply button still shows on expired Gygs in the mobile app",
        "Create a story to add dark mode support to the client portal",
        "Structural: refactor the notification handler to use proper enums in the backend",
        "Bug in admin portal: user search filter returns no results with partial names",
        "Add a part-time status badge to the Gygler profile card in the client portal",
    ],
)


if __name__ == "__main__":
    demo.launch()
