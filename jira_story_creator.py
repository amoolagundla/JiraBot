#!/usr/bin/env python3
"""Batch Jira story creator — reads config from .env and creates stories via the Jira REST API."""

import sys
import time
import os
from base64 import b64encode

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

JIRA_URL = os.environ["JIRA_URL"].rstrip("/")
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY = os.environ["JIRA_PROJECT_KEY"]

# ─────────────────────────────────────────────────────────────────────────────
# Define your stories here.
# Each story requires: type, title, description, acceptance_criteria, labels.
# Supported types depend on your Jira project config — common values:
#   "Story", "Task", "Bug", "Epic"
# ─────────────────────────────────────────────────────────────────────────────
STORIES = [
    {
        "type": "Story",
        "title": "Example: Implement user authentication",
        "description": (
            "Users need to securely log in to the application using email and password. "
            "This story covers the login screen, session management, and logout flow."
        ),
        "acceptance_criteria": [
            "User can log in with a valid email and password.",
            "Invalid credentials display a clear error message.",
            "Session persists across page refreshes until explicit logout.",
            "Logout clears the session and redirects to the login screen.",
        ],
        "labels": ["auth", "backend"],
    },
    {
        "type": "Bug",
        "title": "Example: Submit button unresponsive on mobile",
        "description": (
            "The form submit button does not respond to tap events on iOS and Android. "
            "Users are unable to complete the form on mobile devices."
        ),
        "acceptance_criteria": [
            "Tapping the submit button on iOS triggers form submission.",
            "Tapping the submit button on Android triggers form submission.",
            "No regression on desktop behaviour.",
        ],
        "labels": ["mobile", "bug"],
    },
    {
        "type": "Story",
        "title": "Example: Add dark mode support",
        "description": (
            "Implement a dark colour scheme that respects the system-level preference "
            "and can also be toggled manually by the user."
        ),
        "acceptance_criteria": [
            "Application uses dark theme when system preference is set to dark.",
            "User can manually toggle between light and dark mode in settings.",
            "Theme preference is persisted across sessions.",
            "All screens are legible in both themes with sufficient contrast.",
        ],
        "labels": ["ui", "accessibility"],
    },
]


def _auth_header() -> str:
    token = b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    return f"Basic {token}"


def _adf_doc(description: str, acceptance_criteria: list[str]) -> dict:
    """Build an Atlassian Document Format body."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": description}],
            },
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
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": item}],
                            }
                        ],
                    }
                    for item in acceptance_criteria
                ],
            },
        ],
    }


def create_issue(story: dict) -> str:
    """POST a single issue to Jira and return the created issue key."""
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": story["title"],
            "description": _adf_doc(story["description"], story["acceptance_criteria"]),
            "issuetype": {"name": story["type"]},
            "labels": story.get("labels", []),
        }
    }

    response = requests.post(
        f"{JIRA_URL}/rest/api/3/issue",
        json=payload,
        headers={
            "Authorization": _auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["key"]


def main() -> None:
    failed = []

    print(f"Creating {len(STORIES)} issues in project {JIRA_PROJECT_KEY}...")

    for i, story in enumerate(STORIES, start=1):
        try:
            key = create_issue(story)
            print(f"[{i:02d}/{len(STORIES)}] [CREATED] {key}: {story['title']}")
        except requests.HTTPError as exc:
            msg = exc.response.text if exc.response is not None else str(exc)
            print(f"[{i:02d}/{len(STORIES)}] [FAILED]  {story['title']}: {msg}", file=sys.stderr)
            failed.append(story["title"])
        except Exception as exc:  # noqa: BLE001
            print(f"[{i:02d}/{len(STORIES)}] [FAILED]  {story['title']}: {exc}", file=sys.stderr)
            failed.append(story["title"])

        if i < len(STORIES):
            time.sleep(0.15)

    print()
    if failed:
        print(f"{len(failed)} issue(s) failed:", file=sys.stderr)
        for title in failed:
            print(f"  - {title}", file=sys.stderr)
        sys.exit(1)

    print(f"All {len(STORIES)} issues created successfully.")


if __name__ == "__main__":
    main()
