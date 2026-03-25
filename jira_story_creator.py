#!/usr/bin/env python3
"""Creates 21 Jira stories for the Olympus/Gyglers platform backlog."""

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

STORIES = [
    {
        "type": "Defect",
        "title": "Apply button visible for past/ineligible Gygs",
        "description": (
            "The Apply button renders on Gyg detail screens even when the Gyg has already "
            "passed its start date or the current user is ineligible to apply. This creates "
            "a misleading UX and may produce server-side errors when tapped."
        ),
        "acceptance_criteria": [
            "Apply button is hidden for Gygs whose start date is in the past.",
            "Apply button is hidden when the current user does not meet eligibility criteria.",
            "Eligible, upcoming Gygs continue to show the Apply button.",
            "No console errors or network 4xx responses when viewing ineligible Gygs.",
        ],
    },
    {
        "type": "Story",
        "title": "Implement push navigation",
        "description": (
            "Replace the current modal/tab navigation with stack-based push navigation "
            "to enable deep linking and a native-feeling back-stack across the app."
        ),
        "acceptance_criteria": [
            "Navigating to a detail screen pushes it onto the stack with a back affordance.",
            "Hardware back (Android) and swipe-back (iOS) dismiss the top screen correctly.",
            "Deep links route to the correct screen without breaking the stack.",
            "Existing tab navigation is preserved at the root level.",
        ],
    },
    {
        "type": "Defect",
        "title": "Android black status bar",
        "description": (
            "The status bar renders as a solid black bar on Android, obscuring system icons "
            "and conflicting with the app's colour scheme. Expected behaviour is a transparent "
            "or theme-coloured status bar."
        ),
        "acceptance_criteria": [
            "Status bar background matches the active screen's header colour on Android.",
            "Status bar icons are legible (dark icons on light backgrounds, light on dark).",
            "Fix applies to Android API 29+.",
            "iOS status bar is unaffected.",
        ],
    },
    {
        "type": "Story",
        "title": "Remove unwanted menu items",
        "description": (
            "The side/bottom navigation contains menu items that are not yet implemented "
            "or should not be visible to end users in the current release."
        ),
        "acceptance_criteria": [
            "Identified placeholder menu items are removed from the navigation.",
            "Remaining items link to their correct destinations.",
            "No dead routes remain in the router config.",
        ],
    },
    {
        "type": "Story",
        "title": "Earnings and payments screens",
        "description": (
            "Gyglers need to view their earnings history and upcoming payment schedule. "
            "Implement the Earnings and Payments screens backed by the relevant API endpoints."
        ),
        "acceptance_criteria": [
            "Earnings screen lists completed Gygs with amount earned per Gyg.",
            "Payments screen shows upcoming and past payment dates and amounts.",
            "Totals (period and all-time) are displayed.",
            "Screens handle empty state and loading state gracefully.",
            "Data is fetched from the correct API endpoint and cached appropriately.",
        ],
    },
    {
        "type": "Story",
        "title": "Client portal themes",
        "description": (
            "The client portal must support white-labelling via configurable themes "
            "(colours, logo, typography) so each client organisation can brand their portal."
        ),
        "acceptance_criteria": [
            "Theme tokens (primary/secondary colour, logo URL, font) are configurable per client.",
            "Theme is applied globally without page reload.",
            "Default Olympus theme is used when no client theme is set.",
            "Themes are stored and retrieved from the API, not hardcoded.",
        ],
    },
    {
        "type": "Story",
        "title": "Availability API infusion",
        "description": (
            "Integrate the Availability API so that Gyglers can set and update their "
            "availability windows, and the platform can match available Gyglers to open Gygs."
        ),
        "acceptance_criteria": [
            "Gygler can set available days/times via the app.",
            "Availability is persisted via the Availability API.",
            "Gyg matching logic considers Gygler availability.",
            "Changes to availability are reflected immediately without restart.",
        ],
    },
    {
        "type": "Story",
        "title": "Client portal mobile screens",
        "description": (
            "The client portal is currently desktop-only. Implement responsive/mobile "
            "layouts for key client portal screens so clients can manage Gygs on mobile."
        ),
        "acceptance_criteria": [
            "Dashboard, Gyg list, and Gygler roster screens are usable on 375px+ viewports.",
            "Navigation collapses to a mobile-friendly pattern (hamburger/bottom bar).",
            "No horizontal scrolling on screens narrower than 390px.",
            "Existing desktop layouts are unaffected.",
        ],
    },
    {
        "type": "Story",
        "title": "Staging APIs and infrastructure",
        "description": (
            "Provision and configure staging environment APIs and infrastructure so the "
            "team can test end-to-end flows without touching production data."
        ),
        "acceptance_criteria": [
            "Staging App Service / Function Apps are deployed and healthy.",
            "Staging Cosmos DB and Service Bus instances are isolated from production.",
            "CI/CD pipeline deploys to staging on pushes to the develop branch.",
            "Environment-specific config (connection strings, keys) uses staging Key Vault.",
            "Staging base URL is documented in the team wiki.",
        ],
    },
    {
        "type": "Story",
        "title": "iOS and Android production checklist",
        "description": (
            "Complete all tasks required to submit the Gyglers app to the Apple App Store "
            "and Google Play Store, including assets, metadata, and compliance items."
        ),
        "acceptance_criteria": [
            "App icons and splash screens meet store requirements for all required sizes.",
            "Privacy policy and terms of service URLs are set in store listings.",
            "App passes App Store Review guidelines (no private APIs, correct permissions).",
            "App passes Play Store policy review.",
            "Release builds are signed with production certificates/keystores.",
            "Version numbers and build numbers are incremented correctly.",
        ],
    },
    {
        "type": "Defect",
        "title": "Geolocation movement bug",
        "description": (
            "The geolocation tracking feature incorrectly records location when the device "
            "is stationary or produces erratic coordinates during normal movement, "
            "leading to inaccurate attendance/shift records."
        ),
        "acceptance_criteria": [
            "Stationary device does not generate spurious location updates.",
            "Location accuracy filter (e.g. minimum accuracy threshold) is applied.",
            "Recorded coordinates match actual movement within acceptable GPS tolerance.",
            "Background location updates resume correctly after app returns to foreground.",
        ],
    },
    {
        "type": "Defect",
        "title": "Admin screen bugs",
        "description": (
            "Multiple defects have been reported on the admin screens: incorrect data "
            "rendering, broken filters, and unresponsive action buttons. "
            "Investigate and resolve all identified issues."
        ),
        "acceptance_criteria": [
            "Admin user list renders all users without duplicates or missing entries.",
            "Filter and search controls return correct results.",
            "Bulk-action buttons (approve, reject, suspend) execute successfully.",
            "No unhandled exceptions appear in the browser console on admin screens.",
        ],
    },
    {
        "type": "Story",
        "title": "Document upload screen polish",
        "description": (
            "The document upload screen requires UX polish: improve layout, "
            "upload progress feedback, error states, and file-type validation messaging."
        ),
        "acceptance_criteria": [
            "Upload progress indicator is visible and accurate.",
            "Unsupported file types show a clear inline error before upload is attempted.",
            "Successful uploads display a confirmation state (tick/filename).",
            "Screen layout matches the approved design spec.",
        ],
    },
    {
        "type": "Story",
        "title": "Hide document upload notifications after upload",
        "description": (
            "After a Gygler successfully uploads a required document, the notification "
            "badge/banner prompting them to upload that document should be dismissed "
            "automatically and not reappear."
        ),
        "acceptance_criteria": [
            "Upload notification is cleared immediately after successful upload.",
            "Notification does not reappear on subsequent app launches for uploaded documents.",
            "Notification count badge decrements correctly.",
            "If upload fails, notification remains.",
        ],
    },
    {
        "type": "Story",
        "title": "Prodtrim branch push notifications",
        "description": (
            "Wire up push notifications for the prodtrim release branch so that "
            "Gyglers receive relevant alerts (new Gyg, shift reminder, message) "
            "on both iOS and Android in production."
        ),
        "acceptance_criteria": [
            "FCM (Android) and APNs (iOS) tokens are registered on app launch.",
            "Notifications are delivered when app is in background and foreground.",
            "Tapping a notification deep-links to the relevant screen.",
            "Notification preferences are respected (opt-out per category).",
        ],
    },
    {
        "type": "Defect",
        "title": "Onboarding opportunity push notifications not triggering",
        "description": (
            "Push notifications that should fire when a new onboarding opportunity is "
            "assigned to a Gygler are not being delivered. The notification event is "
            "either not being published or not processed by the notification handler."
        ),
        "acceptance_criteria": [
            "Publishing an onboarding opportunity triggers a push notification to the assigned Gygler within 30 seconds.",
            "Notification payload includes opportunity title and a deep-link URL.",
            "Failed delivery is logged and retried up to 3 times.",
            "Fix is verified in staging environment before merge.",
        ],
    },
    {
        "type": "Story",
        "title": "Opportunity details screen polish / refactor",
        "description": (
            "The Opportunity Details screen has accumulated technical debt and "
            "inconsistent styling. Refactor the component structure and polish "
            "the UI to match current design standards."
        ),
        "acceptance_criteria": [
            "Screen layout matches the approved design spec.",
            "Component is split into presentational sub-components with single responsibilities.",
            "All hardcoded strings are moved to constants/i18n.",
            "No performance regressions (no additional re-renders on mount).",
        ],
    },
    {
        "type": "Story",
        "title": "Hide analytics screen",
        "description": (
            "The analytics screen is not ready for end users. Hide it from the "
            "navigation so it is not accessible in production builds while "
            "preserving the route for internal testing."
        ),
        "acceptance_criteria": [
            "Analytics navigation item is not visible to non-admin users in production.",
            "Route still exists and is accessible to admin/internal users via direct URL.",
            "Feature flag or role check controls visibility.",
        ],
    },
    {
        "type": "Story",
        "title": "Talipay infusion",
        "description": (
            "Integrate Talipay as a payment disbursement option so Gyglers can "
            "receive earnings via their Talipay wallet in addition to existing methods."
        ),
        "acceptance_criteria": [
            "Gygler can link a Talipay account in their payment settings.",
            "Earnings disbursement triggers a Talipay payout API call when Talipay is selected.",
            "Payout status (pending/completed/failed) is reflected in the Payments screen.",
            "Failed payouts generate an alert to the finance team.",
            "Integration is covered by unit and integration tests.",
        ],
    },
    {
        "type": "Defect",
        "title": "Onboarding opp shows accept/deny buttons after already accepting",
        "description": (
            "After a Gygler accepts an onboarding opportunity, the Accept and Deny "
            "buttons remain visible on the opportunity card/detail screen. "
            "They should be replaced with a confirmation state."
        ),
        "acceptance_criteria": [
            "Accept/Deny buttons are replaced with an 'Accepted' indicator after acceptance.",
            "State persists across app restarts (backed by API, not local state only).",
            "Tapping Accept a second time does not submit a duplicate acceptance.",
            "Denied opportunities show a 'Declined' indicator instead.",
        ],
    },
    {
        "type": "Story",
        "title": "Turn off debug mode via API call per user",
        "description": (
            "Debug mode is currently a compile-time flag. Implement an API-driven "
            "mechanism so debug logging/features can be toggled per user at runtime "
            "without a new app build."
        ),
        "acceptance_criteria": [
            "API endpoint exists to set/unset debug mode for a given user ID.",
            "App checks debug mode flag on launch and applies it.",
            "Debug logs and UI overlays are gated behind the flag.",
            "Only admin/internal users can modify the debug flag via API.",
            "Flag state is persisted in user profile, not in app storage alone.",
        ],
    },
]


def _auth_header() -> str:
    token = b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    return f"Basic {token}"


def _adf_doc(description: str, acceptance_criteria: list[str]) -> dict:
    """Build an Atlassian Document Format body."""
    ac_items = [
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
    ]

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
                "content": ac_items,
            },
        ],
    }


def create_issue(story: dict) -> str:
    """POST issue to Jira and return the created issue key."""
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": story["title"],
            "description": _adf_doc(story["description"], story["acceptance_criteria"]),
            "issuetype": {"name": story["type"]},
            "labels": ["mobile", "olympus"],
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

    for i, story in enumerate(STORIES, start=1):
        try:
            key = create_issue(story)
            print(f"[CREATED] {key}: {story['title']}")
        except requests.HTTPError as exc:
            msg = exc.response.text if exc.response is not None else str(exc)
            print(f"[FAILED]  {story['title']}: {msg}", file=sys.stderr)
            failed.append(story["title"])
        except Exception as exc:  # noqa: BLE001
            print(f"[FAILED]  {story['title']}: {exc}", file=sys.stderr)
            failed.append(story["title"])

        # Respect Jira Cloud rate limit (~10 req/s; 0.15 s gives comfortable headroom)
        if i < len(STORIES):
            time.sleep(0.15)

    if failed:
        print(f"\n{len(failed)} story/stories failed to create.", file=sys.stderr)
        sys.exit(1)

    print(f"\nAll {len(STORIES)} stories created successfully.")


if __name__ == "__main__":
    main()
