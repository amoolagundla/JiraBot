#!/usr/bin/env python3
"""Creates TaliPay Integration Epic, 11 Phase Features, and links 38 existing stories."""

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

# Stories created in talipay_stories_creator.py (GYG1-836 to GYG1-873)
PHASE_STORIES = {
    0: ["GYG1-836", "GYG1-837", "GYG1-838", "GYG1-839"],
    1: ["GYG1-840", "GYG1-841", "GYG1-842", "GYG1-843", "GYG1-844", "GYG1-845", "GYG1-846", "GYG1-847", "GYG1-848"],
    2: ["GYG1-849", "GYG1-850", "GYG1-851", "GYG1-852"],
    3: ["GYG1-853", "GYG1-854", "GYG1-855", "GYG1-856"],
    4: ["GYG1-857", "GYG1-858", "GYG1-859"],
    5: ["GYG1-860", "GYG1-861", "GYG1-862"],
    6: ["GYG1-863", "GYG1-864"],
    7: ["GYG1-865", "GYG1-866", "GYG1-867", "GYG1-868"],
    8: ["GYG1-869", "GYG1-870"],
    9: ["GYG1-871"],
    10: ["GYG1-872", "GYG1-873"],
}

PHASES = [
    {
        "phase": 0,
        "name": "Phase 0: Hardening Prerequisites",
        "description": "Financial System Safety Infrastructure. BLOCKER — must complete before any TaliPay code. Prevents the 7 known production failure modes: duplicate processing, blind retries, race conditions, slow queries, duplicate API calls, partial invoices, silent drift.",
        "priority": "BLOCKER",
        "stories_count": 4,
        "endpoints": 0,
    },
    {
        "phase": 1,
        "name": "Phase 1: Foundation + Entity Sync",
        "description": "TaliPay Foundation Infrastructure & Customer/Vendor Sync. Establishes the HTTP client, mapping container, idempotency, audit service, and syncs Locations -> TaliPay Customers and Gyglers -> TaliPay Vendors.",
        "priority": "Must Have",
        "stories_count": 9,
        "endpoints": 7,
    },
    {
        "phase": 2,
        "name": "Phase 2: Shift Sync",
        "description": "Pass Approved Gygs to TaliPay as Pre-Rated Shifts. Implements the PaymentSyncStatus state machine, shift creation service, sync subscriber, and smart retry function.",
        "priority": "Must Have",
        "stories_count": 4,
        "endpoints": 5,
    },
    {
        "phase": 3,
        "name": "Phase 3: Invoicing",
        "description": "Automated Customer & Vendor Invoice Creation. Atomic batch invoicing with distributed locking, inline reconciliation, and rollback on partial failure.",
        "priority": "Must Have",
        "stories_count": 4,
        "endpoints": 11,
    },
    {
        "phase": 4,
        "name": "Phase 4: Credit Notes + Custom Line Items",
        "description": "Invoice Adjustments. Credit note CRUD + apply/unapply and custom line item support on TaliPay invoices.",
        "priority": "Should Have",
        "stories_count": 3,
        "endpoints": 10,
    },
    {
        "phase": 5,
        "name": "Phase 5: Payments",
        "description": "PAYG Deposits & Factored Customer Payments. Payment reference CRUD, PAYG deposit debit on invoice completion, and factored payment recording.",
        "priority": "Must Have",
        "stories_count": 3,
        "endpoints": 9,
    },
    {
        "phase": 6,
        "name": "Phase 6: Taxes",
        "description": "Tax Configuration & Application. Tax CRUD and bulk apply/clear on shift line items.",
        "priority": "Should Have",
        "stories_count": 2,
        "endpoints": 10,
    },
    {
        "phase": 7,
        "name": "Phase 7: Webhooks + Event Sync",
        "description": "TaliPay Webhook Ingestion with State Guards. Handles out-of-order delivery, dedup, deferred processing for missing dependencies, and near-real-time reconciliation.",
        "priority": "Must Have",
        "stories_count": 4,
        "endpoints": 8,
    },
    {
        "phase": 8,
        "name": "Phase 8: Vendor Early-Pay",
        "description": "Vendor Early-Pay Flow Through Olympus. Eligibility check and early-pay request endpoints for Gygler vendors.",
        "priority": "Nice to Have",
        "stories_count": 2,
        "endpoints": 4,
    },
    {
        "phase": 9,
        "name": "Phase 9: Attachments + PDF",
        "description": "Invoice Attachments & PDF. Upload, list, delete attachments and stream invoice PDFs.",
        "priority": "Nice to Have",
        "stories_count": 1,
        "endpoints": 5,
    },
    {
        "phase": 10,
        "name": "Phase 10: Reconciliation + Monitoring",
        "description": "Multi-Layer Reconciliation & Financial Integrity. Three-layer daily reconciliation (entity sync, shift/invoice check, financial amount check) plus dashboard endpoints.",
        "priority": "Must Have",
        "stories_count": 2,
        "endpoints": 7,
    },
]


def _auth_header() -> str:
    token = b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    return f"Basic {token}"


def _headers() -> dict:
    return {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _adf_paragraph(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


def create_issue(payload: dict) -> str:
    r = requests.post(
        f"{JIRA_URL}/rest/api/3/issue",
        json=payload,
        headers=_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["key"]


def set_parent(issue_key: str, parent_key: str) -> None:
    r = requests.put(
        f"{JIRA_URL}/rest/api/3/issue/{issue_key}",
        json={"fields": {"parent": {"key": parent_key}}},
        headers=_headers(),
        timeout=30,
    )
    r.raise_for_status()


def main() -> None:
    # ── 1. Create Epic ────────────────────────────────────────────────────────
    print("Creating TaliPay Integration Epic...")
    epic_key = create_issue({
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": "TaliPay Integration",
            "description": _adf_paragraph(
                "End-to-end TaliPay financial integration for olympus-functions-onboarding (.NET 8 isolated worker). "
                "Core principle: Olympus = source of truth for WORK. TaliPay = source of truth for MONEY. "
                "11 phases, 38 stories, 76 endpoint scenarios. "
                "MVP = Phases 0+1+2+3+5+7+10 (30 stories, 47 endpoints). "
                "New Cosmos containers: processed-events, financial-summary, external-mappings, "
                "idempotency-keys, financial-audit-log, invoicing-runs, talipay-webhooks."
            ),
            "issuetype": {"name": "Epic"},
            "labels": ["talipay", "onboarding-functions"],
        }
    })
    print(f"  [CREATED] Epic: {epic_key}")
    time.sleep(0.15)

    # ── 2. Create Phase Features under the Epic ───────────────────────────────
    print("\nCreating Phase Features...")
    phase_feature_keys: dict[int, str] = {}

    for phase in PHASES:
        feature_key = create_issue({
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": phase["name"],
                "description": _adf_paragraph(
                    f"{phase['description']} | "
                    f"Priority: {phase['priority']} | "
                    f"Stories: {phase['stories_count']} | "
                    f"TaliPay endpoints: {phase['endpoints']}"
                ),
                "issuetype": {"name": "Feature"},
                "parent": {"key": epic_key},
                "labels": ["talipay", f"phase-{phase['phase']}"],
            }
        })
        phase_feature_keys[phase["phase"]] = feature_key
        print(f"  [CREATED] Feature {feature_key}: {phase['name']}")
        time.sleep(0.15)

    # ── 3. Link stories to their Phase Feature ────────────────────────────────
    print("\nLinking stories to Phase Features...")
    failed = []

    for phase_num, story_keys in PHASE_STORIES.items():
        feature_key = phase_feature_keys[phase_num]
        for story_key in story_keys:
            try:
                set_parent(story_key, feature_key)
                print(f"  [LINKED] {story_key} -> {feature_key} (Phase {phase_num})")
            except requests.HTTPError as exc:
                msg = exc.response.text if exc.response is not None else str(exc)
                print(f"  [FAILED] {story_key}: {msg}", file=sys.stderr)
                failed.append(story_key)
            time.sleep(0.15)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 50)
    print(f"Epic:     {epic_key} — TaliPay Integration")
    for phase in PHASES:
        fk = phase_feature_keys[phase["phase"]]
        print(f"  {fk}: {phase['name']}")
    print()

    if failed:
        print(f"{len(failed)} stories failed to link: {failed}", file=sys.stderr)
        sys.exit(1)

    print(f"All 38 stories linked successfully.")


if __name__ == "__main__":
    main()
