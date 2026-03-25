#!/usr/bin/env python3
"""Conversational Jira story creator — describe work in plain English, Claude creates the issues."""

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
            f"Create a single Jira issue in project {JIRA_PROJECT_KEY}. "
            "Use Story for features and improvements, Bug for defects. "
            "Write clear, testable acceptance criteria."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Concise issue title",
                },
                "issue_type": {
                    "type": "string",
                    "enum": ["Story", "Bug", "Task"],
                    "description": "Story for features, Bug for defects, Task for chores",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed context and problem statement",
                },
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific, testable acceptance criteria (3-6 items)",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relevant labels, e.g. ['mobile', 'backend', 'bug']",
                },
            },
            "required": ["summary", "issue_type", "description", "acceptance_criteria", "labels"],
        },
    }
]

SYSTEM_PROMPT = f"""You are a Jira story creation assistant for project {JIRA_PROJECT_KEY}.

When the user describes work items — in any format, including rough notes or meeting transcripts — extract each distinct item and create a well-structured Jira issue using the create_jira_issue tool.

Guidelines:
- Story: new features, improvements, enhancements
- Bug: something broken or behaving incorrectly
- Task: chores, configuration, non-feature work
- Write 3-6 specific, testable acceptance criteria per issue
- Keep summaries under 80 characters
- Apply sensible labels based on area (e.g. mobile, api, ui, backend, auth)

After creating all issues, reply with a concise table:
| Key | Title | Type |"""

anthropic_client = anthropic.Anthropic()


def respond(message: str, history: list) -> Generator[str, None, None]:
    """Stream Claude's response and execute Jira tool calls."""
    messages = []
    for turn in history:
        if isinstance(turn, dict):
            messages.append({"role": turn["role"], "content": turn["content"]})
        else:
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
    title="Jira Story Creator",
    description=(
        "Describe backlog items in plain English — paste meeting notes, bullet points, "
        "or rough requirements — and the agent will create structured Jira issues automatically."
    ),
    examples=[
        "Add a bug: the login button doesn't work on Safari mobile",
        "Story: users should be able to export their data as a CSV from the dashboard",
        "The notification emails are going to spam — needs investigation",
        "Add two-factor authentication support to the user account settings",
        "Bug: the date picker crashes when the user selects a past date",
    ],
)

if __name__ == "__main__":
    demo.launch()
