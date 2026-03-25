#!/usr/bin/env python3
"""Creates the TaliPay Integration Confluence page in the Software Development space."""

import os
import requests
from base64 import b64encode
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

JIRA_URL = os.environ["JIRA_URL"].rstrip("/")
CONFLUENCE_URL = JIRA_URL.replace("https://", "https://") + "/wiki" if "/wiki" not in JIRA_URL else JIRA_URL
CONFLUENCE_URL = f"https://{JIRA_URL.split('//')[1].split('/')[0]}/wiki"
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
SPACE_ID = os.environ["CONFLUENCE_SPACE_ID"]
PARENT_PAGE_ID = os.environ["CONFLUENCE_PARENT_PAGE_ID"]


def _auth_header() -> str:
    token = b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    return f"Basic {token}"


def _headers() -> dict:
    return {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def code_block(content: str, language: str = "text") -> str:
    escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<ac:structured-macro ac:name="code" ac:schema-version="1">'
        f'<ac:parameter ac:name="language">{language}</ac:parameter>'
        f'<ac:parameter ac:name="theme">Midnight</ac:parameter>'
        f'<ac:plain-text-body><![CDATA[{content}]]></ac:plain-text-body>'
        f'</ac:structured-macro>'
    )


def info_box(content: str) -> str:
    return (
        f'<ac:structured-macro ac:name="info" ac:schema-version="1">'
        f'<ac:rich-text-body><p>{content}</p></ac:rich-text-body>'
        f'</ac:structured-macro>'
    )


def warning_box(content: str) -> str:
    return (
        f'<ac:structured-macro ac:name="warning" ac:schema-version="1">'
        f'<ac:rich-text-body><p>{content}</p></ac:rich-text-body>'
        f'</ac:structured-macro>'
    )


def panel(title: str, content: str) -> str:
    return (
        f'<ac:structured-macro ac:name="panel" ac:schema-version="1">'
        f'<ac:parameter ac:name="title">{title}</ac:parameter>'
        f'<ac:rich-text-body>{content}</ac:rich-text-body>'
        f'</ac:structured-macro>'
    )


def toc() -> str:
    return (
        '<ac:structured-macro ac:name="toc" ac:schema-version="1">'
        '<ac:parameter ac:name="maxLevel">3</ac:parameter>'
        '</ac:structured-macro>'
    )


PAGE_CONTENT = f"""
{warning_box("<strong>BLOCKER:</strong> Phase 0 must be completed before any TaliPay code is written. These are the safety nets that prevent known production failure modes.")}

{info_box("<strong>Core Principle:</strong> Olympus = source of truth for WORK. TaliPay = source of truth for MONEY.")}

{toc()}

<h1>Overview</h1>
<p>This document describes the full TaliPay financial integration for <code>olympus-functions-onboarding</code> (.NET 8 isolated worker, Azure Functions). The integration spans 11 phases, 38 stories, and 76 endpoint scenarios.</p>
<table>
  <tbody>
    <tr><th>Project</th><td>olympus-functions-onboarding (Azure Functions, .NET 8)</td></tr>
    <tr><th>Integration</th><td>TaliPay financial platform</td></tr>
    <tr><th>Jira Epic</th><td>GYG1-874 — TaliPay Integration</td></tr>
    <tr><th>Total Phases</th><td>11 (Phase 0 + Phases 1–10)</td></tr>
    <tr><th>Total Stories</th><td>38</td></tr>
    <tr><th>TaliPay Endpoints</th><td>76</td></tr>
    <tr><th>MVP Scope</th><td>Phases 0+1+2+3+5+7+10 = 30 stories, 47 endpoints</td></tr>
  </tbody>
</table>

<h1>System Architecture</h1>

{code_block("""
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              OLYMPUS ECOSYSTEM                                  │
│                                                                                 │
│  ┌──────────────────┐    ┌──────────────────────┐    ┌───────────────────────┐  │
│  │  Olympus Web API  │    │  Olympus Dashboard    │    │  Gygler Mobile App    │  │
│  │  (ASP.NET Core)   │    │  (Angular)            │    │  (Capacitor)          │  │
│  └────────┬──────────┘    └──────────┬────────────┘    └───────────┬───────────┘  │
│           │                          │                              │              │
│           └──────────────┬───────────┘                              │              │
│                          ▼                                          │              │
│  ┌───────────────────────────────────────────────────────────────────────────┐   │
│  │                         AZURE SERVICE BUS                                 │   │
│  │                                                                           │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │ location-    │  │ gygler-      │  │ gyg-events   │  │ talipay-     │  │   │
│  │  │ events       │  │ events       │  │              │  │ alerts       │  │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │   │
│  └─────────┼─────────────────┼─────────────────┼─────────────────┼───────────┘   │
│            │                 │                 │                  │               │
│            ▼                 ▼                 ▼                  ▼               │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │            OLYMPUS-FUNCTIONS-ONBOARDING  (Azure Functions .NET 8)        │    │
│  │                                                                          │    │
│  │  ┌── SERVICE BUS SUBSCRIBERS ──────────────────────────────────────┐     │    │
│  │  │  LocationSyncSubscriber  ──► TaliPayCustomerService             │     │    │
│  │  │  GyglerSyncSubscriber    ──► TaliPayVendorService               │     │    │
│  │  │  GygShiftSyncSubscriber  ──► TaliPayShiftService                │     │    │
│  │  │  PaygDepositDebitFunc    ──► TaliPayPaymentService              │     │    │
│  │  └─────────────────────────────────────────────────────────────────┘     │    │
│  │                                                                          │    │
│  │  ┌── TIMER FUNCTIONS ──────────────────────────────────────────────┐     │    │
│  │  │  InvoicingTimerFunction   (2am daily)  ──► TaliPayInvoiceSvc    │     │    │
│  │  │  ShiftSyncRetryFunction   (every 15m)  ──► TaliPayShiftSvc      │     │    │
│  │  │  WebhookDeferredProcessor (every  5m)  ──► TaliPayWebhookSvc    │     │    │
│  │  │  ReconciliationFunction   (6am daily)  ──► All Services         │     │    │
│  │  └─────────────────────────────────────────────────────────────────┘     │    │
│  │                                                                          │    │
│  │  ┌── HTTP FUNCTIONS ───────────────────────────────────────────────┐     │    │
│  │  │  POST /api/webhooks/talipay      ◄── TaliPay Webhook Push       │     │    │
│  │  │  GET  /api/talipay/health                                       │     │    │
│  │  │  POST /api/talipay/invoicing/run                                │     │    │
│  │  │  GET  /api/talipay/summary/{locationId}                         │     │    │
│  │  │  POST /api/talipay/credit-notes                                 │     │    │
│  │  │  POST /api/talipay/payments/factored                            │     │    │
│  │  │  GET  /api/talipay/reconciliation/status                        │     │    │
│  │  │  POST /api/talipay/reconciliation/run                           │     │    │
│  │  │  GET  /api/talipay/vendors/{gyglerId}/early-pay                 │     │    │
│  │  │  GET  /api/talipay/invoices/{id}/pdf                            │     │    │
│  │  └─────────────────────────────────────────────────────────────────┘     │    │
│  │                                                                          │    │
│  │  ┌── SHARED SERVICES ──────────────────────────────────────────────┐     │    │
│  │  │  TaliPayClient (HttpClient + Polly: retry 3x exp, circuit-break)│     │    │
│  │  │  EventIdempotencyService  (processed-events container)          │     │    │
│  │  │  IdempotencyService       (idempotency-keys container)          │     │    │
│  │  │  ExternalMappingRepository (Olympus ID ↔ TaliPay ID)            │     │    │
│  │  │  ErrorClassifier          (Transient/DependencyMissing/Validation│     │    │
│  │  │  FinancialAuditService    (fire-and-forget, Channel-based)      │     │    │
│  │  │  FinancialSummaryService  (denormalized read model per location) │     │    │
│  │  └─────────────────────────────────────────────────────────────────┘     │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐   │
│  │                          AZURE COSMOS DB                                  │   │
│  │                                                                           │   │
│  │  Existing                    New (TaliPay Phase 0–7)                      │   │
│  │  ──────────────────          ─────────────────────────────────────────    │   │
│  │  gygs                        processed-events    PK:/eventId  TTL:30d     │   │
│  │  gyglers                     financial-summary   PK:/locationId           │   │
│  │  organizations               external-mappings   PK:/internalId           │   │
│  │  client-orgs                 idempotency-keys    PK:/key       TTL:7d     │   │
│  │  gyg-attendance              financial-audit-log PK:/datePart  TTL:365d   │   │
│  │  event-log                   invoicing-runs      PK:/runDate              │   │
│  │                              talipay-webhooks    PK:/eventType TTL:30d    │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└──────────────────────────────────────────────────────────┬───────────────────────┘
                                                           │
                                        HTTPS (Bearer API Key)
                                                           │
                                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              TALIPAY PLATFORM                                   │
│                         https://uat.talipay.com/api/v1                          │
│                                                                                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐ │
│  │  Customers    │  │  Vendors      │  │  Shifts       │  │  Invoices         │ │
│  │  (=Locations) │  │  (=Gyglers)   │  │  (=Gygs)      │  │  (Cust + Vendor)  │ │
│  └───────────────┘  └───────────────┘  └───────────────┘  └───────────────────┘ │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐ │
│  │  Credit Notes │  │  Payment Refs │  │  Taxes        │  │  Webhooks/Events  │ │
│  └───────────────┘  └───────────────┘  └───────────────┘  └───────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
""")}

<h1>Entity Mapping</h1>
<p>How Olympus domain objects map to TaliPay concepts:</p>
<table>
  <tbody>
    <tr><th>Olympus</th><th>TaliPay</th><th>Sync Direction</th><th>Trigger</th></tr>
    <tr><td>Location (client org)</td><td>Customer</td><td>Olympus → TaliPay</td><td>location-events Service Bus</td></tr>
    <tr><td>Gygler</td><td>Vendor</td><td>Olympus → TaliPay</td><td>gygler-events Service Bus</td></tr>
    <tr><td>Gyg (approved)</td><td>Shift (pre_rated=true)</td><td>Olympus → TaliPay</td><td>gyg-events Service Bus</td></tr>
    <tr><td>Invoicing Run</td><td>Invoice (Customer + Vendor)</td><td>Olympus → TaliPay</td><td>2am timer</td></tr>
    <tr><td>Payment</td><td>Payment Reference</td><td>Bidirectional</td><td>Webhook / HTTP</td></tr>
  </tbody>
</table>

<h1>PaymentSyncStatus State Machine</h1>

{code_block("""
                    ┌─────────────┐
                    │  NotSynced  │  (Gyg approved, shift not yet sent to TaliPay)
                    └──────┬──────┘
                           │
                    Gyg approved event → GygShiftSyncSubscriber
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
         ┌──────────────┐    ┌──────────────────┐
         │ ShiftSynced  │    │ ShiftSyncFailed   │◄──── ShiftSyncRetryFunction (15m)
         │              │    │                  │       - Transient: retry
         └──────┬───────┘    │ (DependencyMissing│      - Validation: skip + alert
                │            │  = no customer/   │      - Max retries: alert admin
                │            │  vendor mapping)  │
                │            └──────────────────┘
         2am InvoicingTimerFunction
                │
                ▼
         ┌──────────────┐
         │   Invoiced   │  (included in TaliPay customer + vendor invoices)
         └──────┬───────┘
                │
         TaliPay webhook: invoice.paid
         → TaliPayWebhookFunction
                │
                ▼
         ┌──────────────┐
         │    Paid      │  (payment confirmed by TaliPay)
         └──────────────┘

  Rollback: invoice.voided webhook → Invoiced → ShiftSynced
""")}

<h1>Key Flows</h1>

<h2>Sync Flow (Olympus → TaliPay)</h2>

{code_block("""
  Location Created ──► Service Bus ──► LocationSyncSubscriber
                                           │
                                           ├─► EventIdempotencyService.Check(eventId)
                                           │     └─ if already processed → skip
                                           ├─► IdempotencyService.Check(key)
                                           ├─► TaliPayClient.POST /v1/customers
                                           ├─► ExternalMappingRepo.Create(locationId, customerId)
                                           ├─► FinancialSummaryService.SetCustomerId()
                                           ├─► FinancialAuditService.Log(CustomerCreated)
                                           └─► EventIdempotencyService.MarkProcessed(eventId)

  Gygler Onboarded ──► Service Bus ──► GyglerSyncSubscriber
                                           └─► (same pattern → POST /v1/vendors)

  Gyg Approved ────► Service Bus ──► GygShiftSyncSubscriber
                                           │
                                           ├─► EventIdempotencyService.Check()
                                           ├─► ExternalMappingRepo.Get(locationId) → customerId
                                           ├─► ExternalMappingRepo.Get(gyglerId)   → vendorId
                                           │     └─ if missing → DependencyMissing error
                                           │          → abandon + pending-sync record + alert
                                           ├─► TaliPayClient.POST /v1/shifts
                                           │     { pre_rated: true, customer_id, vendor_id,
                                           │       customer_amount, vendor_amount }
                                           ├─► GygBase.PaymentSyncStatus = ShiftSynced
                                           └─► FinancialAuditService.Log(ShiftSynced)
""")}

<h2>Invoicing Flow (2am Timer)</h2>

{code_block("""
  2am Timer ──► InvoicingTimerFunction
                    │
                    ├─► 1. Acquire distributed lock
                    │         InvoicingRun { LockHolder, LockExpiresAt: +30min }
                    │         (if lock exists and not expired → skip, another instance running)
                    │
                    ├─► 2. PREPARE PHASE
                    │         Query gygs WHERE status=Approved
                    │                    AND PaymentSyncStatus=ShiftSynced
                    │                    AND completedAt within cutoff window
                    │                    AND InvoicingRunId IS NULL
                    │         Generate InvoiceBatchId, stamp all gygs
                    │
                    ├─► 3. VALIDATE PHASE (inline reconciliation)
                    │         For each gyg: verify shift exists in TaliPay
                    │         If shift missing → sync now OR exclude from batch
                    │         If validation fails completely → abort, alert, release lock
                    │
                    ├─► 4. EXECUTE PHASE
                    │         POST /v1/invoices { type: customer, shift_ids: [...] }
                    │         POST /v1/invoices { type: vendor, shift_ids: [...] }
                    │           (one per vendor, grouped)
                    │
                    ├─► 5. CONFIRM PHASE
                    │         If customer OK but vendor fails → void customer invoice → alert
                    │         (atomicity: both succeed or both rolled back)
                    │
                    ├─► 6. UPDATE
                    │         GygBase.PaymentSyncStatus = Invoiced
                    │         GygBase.InvoicingRunId = runId
                    │         FinancialSummary.TotalInvoicedCents += amount
                    │
                    └─► 7. Release lock (InvoicingRun.Status = Completed)

  Crash recovery: lock expires → next timer run picks up → InvoiceBatchId prevents re-stamping
""")}

<h2>Payment Flow</h2>

{code_block("""
  PAYG Customer (factoring_eligible = false):
  ─────────────────────────────────────────
  Invoice Created
    └─► PaygDepositDebitFunction (Service Bus trigger)
          ├─► POST /v1/payment_references { amount: depositBalance }
          ├─► POST /v1/invoices/{id}/apply_payment_reference
          ├─► if deposit < invoice → flag for top-up, alert finance
          └─► FinancialSummary.TotalPaidCents += amount

  Factored Customer (factoring_eligible = true):
  ────────────────────────────────────────────
  Customer Pays at Terms
    └─► POST /api/talipay/payments/factored
          ├─► POST /v1/payment_references { amount, due_date }
          ├─► POST /v1/invoices/{id}/apply_payment_reference
          └─► FinancialSummary updated
""")}

<h2>Webhook Flow (TaliPay → Olympus)</h2>

{code_block("""
  TaliPay Event ──► POST /api/webhooks/talipay
                        │
                        ├─► 1. Dedup check
                        │         if TaliPayEventId already Processed → return 200
                        │
                        ├─► 2. State guard
                        │         invoice.paid   → requires PaymentSyncStatus == Invoiced
                        │         vendor.paid    → requires vendor invoice exists
                        │         credit_note.*  → requires invoice exists
                        │
                        ├─► 3. Deferred processing (if dependency missing)
                        │         Store as PendingDependency
                        │         WebhookDeferredProcessorFunction retries every 5min
                        │         Max 3 attempts → alert admin
                        │
                        ├─► 4. State transitions
                        │         invoice.paid   → PaymentSyncStatus = Paid
                        │                        + FinancialSummary.TotalPaidCents
                        │         invoice.voided → PaymentSyncStatus = ShiftSynced (rollback)
                        │         vendor.paid    → vendor payment status updated
                        │
                        ├─► 5. Near-real-time reconciliation
                        │         Verify amount in webhook matches stored amount
                        │
                        └─► Return 200 on success, 500 on error (TaliPay retries on 5xx)
""")}

<h2>Reconciliation Flow (6am Timer)</h2>

{code_block("""
  6am Timer ──► ReconciliationTimerFunction
                    │
                    ├─► LAYER 1: Entity Sync Check
                    │     GET /v1/customers (paginated, 20/page)
                    │       ←→ ExternalMappings WHERE EntityType=Customer
                    │     GET /v1/vendors (paginated)
                    │       ←→ ExternalMappings WHERE EntityType=Vendor
                    │     Missing in TaliPay → auto-re-sync + log ReconciliationFixed
                    │
                    ├─► LAYER 2: Shift + Invoice Check
                    │     All gygs with ShiftSynced → verify shift exists in TaliPay
                    │     All gygs with Invoiced    → verify invoice exists
                    │     Shift counts per invoice must match
                    │
                    ├─► LAYER 3: Financial Amount Check
                    │     Invoice amounts in TaliPay ←→ FinancialSummary
                    │     Payment totals ←→ FinancialSummary
                    │     Outstanding balance ←→ FinancialSummary
                    │
                    ├─► On CRITICAL mismatch (amount wrong, invoice missing)
                    │     → financial-audit-log: Action=ReconciliationMismatch
                    │     → Immediate admin alert via talipay-alerts
                    │
                    └─► Update FinancialSummary.ReconciliationStatus + LastReconciliationDate
""")}

<h1>Safety Infrastructure (Phase 0)</h1>

{warning_box("All four Phase 0 stories are blockers. No TaliPay API code may be written until these are in place.")}

<h2>Dual Idempotency Layers</h2>
<table>
  <tbody>
    <tr><th>Layer</th><th>Container</th><th>Prevents</th><th>Story</th></tr>
    <tr><td>Event-level</td><td>processed-events (TTL 30d)</td><td>Function processing same Service Bus message twice on retry/crash</td><td>GYG1-836 (0.1)</td></tr>
    <tr><td>API-level</td><td>idempotency-keys (TTL 7d)</td><td>Calling TaliPay API twice for the same logical operation</td><td>GYG1-842 (1.3)</td></tr>
  </tbody>
</table>

<h2>Error Classification</h2>
<table>
  <tbody>
    <tr><th>Error Type</th><th>Examples</th><th>Action</th></tr>
    <tr><td>Transient</td><td>Timeout, 5xx, network error</td><td>Abandon (Service Bus retries with backoff)</td></tr>
    <tr><td>DependencyMissing</td><td>No vendor mapping, no customer mapping</td><td>Abandon + create pending-sync record + alert admin</td></tr>
    <tr><td>Validation</td><td>400, 422 from TaliPay</td><td>Dead-letter immediately, never retry</td></tr>
    <tr><td>RateLimit</td><td>429 from TaliPay</td><td>Abandon with backoff respecting Retry-After header</td></tr>
    <tr><td>Outage</td><td>3+ consecutive transient failures</td><td>Trip circuit breaker + alert admin</td></tr>
  </tbody>
</table>

<h2>Production Safety Matrix</h2>
<table>
  <tbody>
    <tr><th>Failure Mode</th><th>Prevention Mechanism</th><th>Phase</th></tr>
    <tr><td>Duplicate shifts from Service Bus retries</td><td>Event-level idempotency (processed-events)</td><td>0</td></tr>
    <tr><td>Blind retry on dependency failures</td><td>Error classification service</td><td>0</td></tr>
    <tr><td>Race conditions between concurrent functions</td><td>ETag concurrency on all Cosmos updates</td><td>0</td></tr>
    <tr><td>Slow &quot;what does customer owe?&quot; queries</td><td>Financial read model (financial-summary)</td><td>0</td></tr>
    <tr><td>Duplicate TaliPay API calls</td><td>API-level idempotency (idempotency-keys)</td><td>1</td></tr>
    <tr><td>Partial invoices from function crash</td><td>Atomic batch preparation + InvoiceBatchId + distributed lock</td><td>3</td></tr>
    <tr><td>Out-of-order webhooks</td><td>State guards + deferred processing</td><td>7</td></tr>
    <tr><td>Silent data drift</td><td>Multi-layer reconciliation (inline + near-RT + daily)</td><td>10</td></tr>
  </tbody>
</table>

<h1>New Cosmos DB Containers</h1>
<table>
  <tbody>
    <tr><th>Container</th><th>Phase</th><th>Partition Key</th><th>TTL</th><th>Purpose</th></tr>
    <tr><td>processed-events</td><td>0</td><td>/eventId</td><td>30 days</td><td>Event-level dedup — prevents double-processing on Service Bus retry</td></tr>
    <tr><td>financial-summary</td><td>0</td><td>/locationId</td><td>None</td><td>Denormalized read model — single-query answer to outstanding balance</td></tr>
    <tr><td>external-mappings</td><td>1</td><td>/internalId</td><td>None</td><td>Olympus ID ↔ TaliPay ID lookup table</td></tr>
    <tr><td>idempotency-keys</td><td>1</td><td>/key</td><td>7 days</td><td>API-level dedup — prevents duplicate TaliPay calls</td></tr>
    <tr><td>financial-audit-log</td><td>1</td><td>/datePartition</td><td>365 days</td><td>Immutable money audit trail (fire-and-forget)</td></tr>
    <tr><td>invoicing-runs</td><td>3</td><td>/runDate</td><td>None</td><td>Distributed lock + progress checkpoint for invoicing jobs</td></tr>
    <tr><td>talipay-webhooks</td><td>7</td><td>/eventType</td><td>30 days</td><td>Webhook dedup + deferred processing state</td></tr>
  </tbody>
</table>

<h1>Function Registry</h1>
<table>
  <tbody>
    <tr><th>Function</th><th>Trigger</th><th>Phase</th><th>Jira</th></tr>
    <tr><td>LocationSyncSubscriber</td><td>Service Bus — location-events / talipay-sync</td><td>1</td><td>GYG1-846</td></tr>
    <tr><td>GyglerSyncSubscriber</td><td>Service Bus — gygler-events / talipay-sync</td><td>1</td><td>GYG1-847</td></tr>
    <tr><td>TaliPayHealthCheckFunction</td><td>HTTP GET /api/talipay/health</td><td>1</td><td>GYG1-848</td></tr>
    <tr><td>GygShiftSyncSubscriber</td><td>Service Bus — gyg-events / talipay-shift-sync</td><td>2</td><td>GYG1-851</td></tr>
    <tr><td>ShiftSyncRetryFunction</td><td>Timer every 15 minutes</td><td>2</td><td>GYG1-852</td></tr>
    <tr><td>InvoicingTimerFunction</td><td>Timer 0 0 2 * * * (2am daily)</td><td>3</td><td>GYG1-855</td></tr>
    <tr><td>ManualInvoicingFunction</td><td>HTTP POST /api/talipay/invoicing/run</td><td>3</td><td>GYG1-856</td></tr>
    <tr><td>CreditNoteManagementFunction</td><td>HTTP</td><td>4</td><td>GYG1-859</td></tr>
    <tr><td>PaygDepositDebitFunction</td><td>Service Bus (post-invoicing event)</td><td>5</td><td>GYG1-861</td></tr>
    <tr><td>FactoredPaymentFunction</td><td>HTTP POST /api/talipay/payments/factored</td><td>5</td><td>GYG1-862</td></tr>
    <tr><td>TaxManagementFunction</td><td>HTTP</td><td>6</td><td>GYG1-864</td></tr>
    <tr><td>TaliPayWebhookFunction</td><td>HTTP POST /api/webhooks/talipay</td><td>7</td><td>GYG1-866</td></tr>
    <tr><td>WebhookDeferredProcessorFunction</td><td>Timer every 5 minutes</td><td>7</td><td>GYG1-867</td></tr>
    <tr><td>WebhookManagementFunction</td><td>HTTP</td><td>7</td><td>GYG1-868</td></tr>
    <tr><td>EarlyPayFunction</td><td>HTTP</td><td>8</td><td>GYG1-869, GYG1-870</td></tr>
    <tr><td>InvoiceAttachmentFunction</td><td>HTTP</td><td>9</td><td>GYG1-871</td></tr>
    <tr><td>ReconciliationTimerFunction</td><td>Timer 0 0 6 * * * (6am daily)</td><td>10</td><td>GYG1-872</td></tr>
    <tr><td>ReconciliationDashboardFunction</td><td>HTTP</td><td>10</td><td>GYG1-873</td></tr>
  </tbody>
</table>

<h1>Phase Summary</h1>
<table>
  <tbody>
    <tr><th>Phase</th><th>Epic</th><th>Stories</th><th>Endpoints</th><th>Priority</th><th>Jira Feature</th></tr>
    <tr><td>0</td><td>Hardening Prerequisites</td><td>4</td><td>0</td><td>BLOCKER</td><td>GYG1-875</td></tr>
    <tr><td>1</td><td>Foundation + Entity Sync</td><td>9</td><td>7</td><td>Must Have</td><td>GYG1-876</td></tr>
    <tr><td>2</td><td>Shift Sync</td><td>4</td><td>5</td><td>Must Have</td><td>GYG1-877</td></tr>
    <tr><td>3</td><td>Invoicing</td><td>4</td><td>11</td><td>Must Have</td><td>GYG1-878</td></tr>
    <tr><td>4</td><td>Credit Notes + Custom Items</td><td>3</td><td>10</td><td>Should Have</td><td>GYG1-879</td></tr>
    <tr><td>5</td><td>Payments</td><td>3</td><td>9</td><td>Must Have</td><td>GYG1-880</td></tr>
    <tr><td>6</td><td>Taxes</td><td>2</td><td>10</td><td>Should Have</td><td>GYG1-881</td></tr>
    <tr><td>7</td><td>Webhooks + Event Sync</td><td>4</td><td>8</td><td>Must Have</td><td>GYG1-882</td></tr>
    <tr><td>8</td><td>Vendor Early-Pay</td><td>2</td><td>4</td><td>Nice to Have</td><td>GYG1-883</td></tr>
    <tr><td>9</td><td>Attachments + PDF</td><td>1</td><td>5</td><td>Nice to Have</td><td>GYG1-884</td></tr>
    <tr><td>10</td><td>Reconciliation + Monitoring</td><td>2</td><td>7</td><td>Must Have</td><td>GYG1-885</td></tr>
    <tr><td><strong>Total</strong></td><td></td><td><strong>38</strong></td><td><strong>76</strong></td><td></td><td>GYG1-874 (Epic)</td></tr>
  </tbody>
</table>

{panel("MVP Scope", "<p><strong>Phases 0 + 1 + 2 + 3 + 5 + 7 + 10</strong> = 30 stories, 47 endpoints</p><p>Excludes: Phase 4 (Credit Notes), Phase 6 (Taxes), Phase 8 (Early-Pay), Phase 9 (Attachments)</p>")}

<h1>TaliPay Client Configuration</h1>
{code_block("""
// appsettings.json
{
  "TaliPay": {
    "BaseUrl": "https://uat.talipay.com/api/v1",
    "ApiKeySecretName": "TaliPayApiKey",          // Key Vault secret name
    "TimeoutSeconds": 30,
    "Retry": {
      "MaxAttempts": 3,
      "BackoffBaseSeconds": 2                     // 2s, 4s, 8s
    },
    "CircuitBreaker": {
      "FailureRatio": 0.5,
      "SamplingDurationSeconds": 30,
      "MinimumThroughput": 5,
      "BreakDurationSeconds": 60
    }
  }
}
""", "json")}
"""


def create_page() -> None:
    payload = {
        "spaceId": SPACE_ID,
        "parentId": PARENT_PAGE_ID,
        "status": "current",
        "title": "TaliPay Integration — olympus-functions-onboarding",
        "body": {
            "representation": "storage",
            "value": PAGE_CONTENT,
        },
    }

    r = requests.post(
        f"{CONFLUENCE_URL}/api/v2/pages",
        json=payload,
        headers=_headers(),
        timeout=30,
    )

    if not r.ok:
        print(f"Failed: {r.status_code}")
        print(r.text[:2000])
        r.raise_for_status()

    data = r.json()
    page_id = data["id"]
    page_url = f"{CONFLUENCE_URL}/spaces/SD/pages/{page_id}"
    print(f"[CREATED] Page ID: {page_id}")
    print(f"[URL]     {page_url}")


if __name__ == "__main__":
    create_page()
