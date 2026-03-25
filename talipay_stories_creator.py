#!/usr/bin/env python3
"""Creates 39 Jira stories for the olympus-functions-onboarding TaliPay integration."""

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
    # ─── PHASE 0: Hardening Prerequisites ────────────────────────────────────
    {
        "title": "[Phase 0.1] Event-Level Idempotency (Processed Events Container)",
        "type": "Story",
        "labels": ["talipay", "phase-0", "infrastructure", "blocker"],
        "description": (
            "Every Service Bus event must be tracked to prevent duplicate processing on retry/crash. "
            "This is SEPARATE from the API-level idempotency — this prevents the function from even calling "
            "TaliPay twice for the same event.\n\n"
            "Why: Function processes event -> crashes AFTER TaliPay call -> Service Bus retries -> "
            "duplicate shift created -> duplicate invoices -> real money issue.\n\n"
            "Event payload contract enforced: { eventId, entityId, eventType, version, timestamp }"
        ),
        "acceptance_criteria": [
            "processed-events container created, PK = /eventId, TTL 30 days.",
            "ProcessedEvent entity: Id, EventId, EntityId, EventType, Version, ProcessedAt, Outcome (Success/Failed/Skipped), Ttl.",
            "Every Service Bus subscriber checks processed-events BEFORE any business logic.",
            "Flow: receive message -> extract eventId -> check processed-events -> if exists: complete + skip -> if not: process -> store processed event -> complete.",
            "Dead-letter replay also checks processed-events (old events cannot create inconsistent state).",
            "Files: Domain/Entities/ProcessedEvent.cs, Application/Interfaces/IEventIdempotencyService.cs, Infrastructure/Services/EventIdempotencyService.cs, Infrastructure/Persistence/ApplicationDbContext.cs (modify), Program.cs (modify).",
        ],
    },
    {
        "title": "[Phase 0.2] Error Classification Service",
        "type": "Story",
        "labels": ["talipay", "phase-0", "infrastructure", "blocker"],
        "description": (
            "Tiered error handling that classifies failures and routes to the correct recovery path. "
            "Stops blind retries on dependency failures.\n\n"
            "Why: Retrying 'vendor mapping not found' 3 times does nothing. Retrying during a 1-hour "
            "TaliPay outage with only 3 attempts means the system never recovers.\n\n"
            "Error types: Transient (retry), DependencyMissing (block + alert + abandon), "
            "Validation (dead-letter), RateLimit (backoff respecting Retry-After), Outage (circuit breaker)."
        ),
        "acceptance_criteria": [
            "ErrorClassifier service categorises exceptions into: Transient, DependencyMissing, Validation, RateLimit, Outage.",
            "Service Bus subscribers use ErrorClassifier to decide: abandon vs dead-letter vs complete.",
            "Alert channel: Service Bus topic talipay-alerts for admin notifications.",
            "DependencyMissing errors create a pending-sync record so they can be resolved and retried.",
            "Circuit breaker trips after 3+ consecutive transient failures; alerts admin.",
            "Files: Services/TaliPay/IErrorClassifier.cs, Services/TaliPay/ErrorClassifier.cs, Services/TaliPay/TaliPayException.cs, Models/TaliPay/ErrorClassification.cs.",
        ],
    },
    {
        "title": "[Phase 0.3] ETag Concurrency on All Entity Updates",
        "type": "Story",
        "labels": ["talipay", "phase-0", "infrastructure", "blocker"],
        "description": (
            "Every Cosmos DB update MUST use optimistic concurrency via ETag. "
            "Prevents race conditions between concurrent functions.\n\n"
            "Why: Webhook marks gyg as Paid while invoicing function is still updating the same gyg "
            "-> last write wins -> data corruption."
        ),
        "acceptance_criteria": [
            "All entities updated by multiple functions get an _etag property.",
            "Repository.UpdateAsync checks ETag: if conflict (412) -> reload entity -> retry update (max 3 times).",
            "Affected entities: GygBase, ExternalMapping, InvoicingRun, TaliPayWebhookEvent.",
            "EF Core Cosmos concurrency token configured: modelBuilder.Entity<GygBase>().Property(e => e.ETag).IsETagConcurrency().",
            "All update paths use DbUpdateConcurrencyException catch with reload + retry.",
            "Files: Infrastructure/Repositories/Repository.cs (modify), Infrastructure/Persistence/ApplicationDbContext.cs (modify), affected domain entities (modify).",
        ],
    },
    {
        "title": "[Phase 0.4] Financial Read Model (Summary Container)",
        "type": "Story",
        "labels": ["talipay", "phase-0", "data-layer", "blocker"],
        "description": (
            "Denormalized financial summary per location. Single-query answer to 'what does this customer owe?'\n\n"
            "Why: Without this, answering 'total outstanding' requires cross-partition queries across gygs, "
            "invoices, payments, mappings = expensive and slow."
        ),
        "acceptance_criteria": [
            "financial-summary container created, PK = /locationId.",
            "FinancialSummary entity: LocationId, TaliPayCustomerId, CustomerName, TotalShiftsSynced, TotalInvoicedCents, TotalPaidCents, OutstandingCents (computed), TotalCreditNotesCents, LastInvoiceDate, LastPaymentDate, LastReconciliationDate, ReconciliationStatus (Clean/Mismatch), UpdatedAt.",
            "Updated by: invoicing function, webhook handler (invoice.paid), payment functions, reconciliation.",
            "Update is atomic: read -> modify -> write with ETag.",
            "HTTP function GET /api/talipay/summary/{locationId} returns FinancialSummary directly.",
            "Files: Domain/Entities/FinancialSummary.cs, Application/Interfaces/IFinancialSummaryService.cs, Infrastructure/Services/FinancialSummaryService.cs, ApplicationDbContext.cs (modify), Program.cs (modify).",
        ],
    },

    # ─── PHASE 1: Foundation + Entity Sync ───────────────────────────────────
    {
        "title": "[Phase 1.1] TaliPay HTTP Client with Resilience",
        "type": "Story",
        "labels": ["talipay", "phase-1", "infrastructure", "must-have"],
        "description": (
            "Typed HTTP client for TaliPay API with Polly retry + circuit breaker. "
            "Foundation for all TaliPay API calls throughout the integration."
        ),
        "acceptance_criteria": [
            "HttpClient registered in DI with base URL from config.",
            "API key sourced from Azure Key Vault.",
            "Polly retry: exponential backoff, 3 retries, only on transient (timeout, 5xx).",
            "Polly circuit breaker: 50% failure ratio, 30s window.",
            "NO retry on 4xx — uses ErrorClassifier from Story 0.2.",
            "Request/response logging with configurable timeout (default 30s).",
            "Returns typed TaliPayException with ErrorClassification.",
            "Files: Application/Interfaces/ITaliPayClient.cs, Infrastructure/Services/TaliPay/TaliPayClient.cs, Program.cs (modify), local.settings.json/appsettings.json (modify).",
        ],
    },
    {
        "title": "[Phase 1.2] External Mapping Container & Repository",
        "type": "Story",
        "labels": ["talipay", "phase-1", "data-layer", "must-have"],
        "description": (
            "Cosmos container tracking Olympus <-> TaliPay ID mappings. "
            "Core lookup table for all entity sync operations."
        ),
        "acceptance_criteria": [
            "external-mappings container created, PK = /internalId.",
            "ExternalMapping entity: Id, InternalId, ExternalId, EntityType, Provider, Status, ErrorMessage, SyncVersion, CreatedAt, UpdatedAt, LastSyncedAt, ETag.",
            "Enums: ExternalEntityType, ExternalProvider, ExternalMappingStatus.",
            "Repository: GetByInternalId, GetByExternalId, Create, Update (with ETag).",
            "All properties use .ToJsonProperty() camelCase; enums use [EnumMember].",
            "Files: Domain/Entities/ExternalMapping.cs, Domain/Enums/ExternalEntityType.cs, Domain/Enums/ExternalProvider.cs, Domain/Enums/ExternalMappingStatus.cs, Application/Interfaces/IExternalMappingRepository.cs, Infrastructure/Repositories/ExternalMappingRepository.cs, ApplicationDbContext.cs (modify).",
        ],
    },
    {
        "title": "[Phase 1.3] Idempotency Service (API-Level)",
        "type": "Story",
        "labels": ["talipay", "phase-1", "infrastructure", "must-have"],
        "description": (
            "Prevents duplicate TaliPay API calls on retry/crash. "
            "Works WITH event idempotency (Story 0.1) as a second safety layer.\n\n"
            "Key format: {entityId}-{action}-v{version}"
        ),
        "acceptance_criteria": [
            "idempotency-keys container created, PK = /key, TTL 7 days.",
            "IdempotencyRecord: Id, Key, Status, ResponseBody, ExternalId, HttpStatusCode, CreatedAt, CompletedAt, Ttl.",
            "Service methods: GetAsync, StartAsync, CompleteAsync, FailAsync.",
            "If Completed -> return cached result.",
            "If Processing + stale (>5 min) -> allow retry.",
            "If Failed -> allow retry.",
            "Race-safe: use ETag on StartAsync to prevent two functions claiming the same key.",
            "Files: Domain/Entities/IdempotencyRecord.cs, Domain/Enums/IdempotencyStatus.cs, Application/Interfaces/IIdempotencyService.cs, Infrastructure/Services/IdempotencyService.cs, ApplicationDbContext.cs (modify).",
        ],
    },
    {
        "title": "[Phase 1.4] Financial Audit Service",
        "type": "Story",
        "labels": ["talipay", "phase-1", "infrastructure", "must-have"],
        "description": (
            "Every money-related action logged with before/after state. "
            "Fire-and-forget via Channel — matches existing EventLogBackgroundWriter pattern. "
            "Never blocks the caller."
        ),
        "acceptance_criteria": [
            "financial-audit-log container created, PK = /datePartition, TTL 365 days.",
            "FinancialAuditEntry: Id, CorrelationId, Action, EntityId, ExternalId, EntityType, ActorId, ActorType, AmountCents, Currency, BeforeState, AfterState, Metadata, Success, ErrorMessage, Timestamp, DatePartition, Ttl.",
            "FinancialAction enum with 18 values covering all money operations.",
            "Fire-and-forget via Channel (never blocks caller).",
            "Files: Domain/Entities/FinancialAuditEntry.cs, Domain/Enums/FinancialAction.cs, Application/Interfaces/IFinancialAuditService.cs, Infrastructure/Services/FinancialAuditService.cs, ApplicationDbContext.cs (modify).",
        ],
    },
    {
        "title": "[Phase 1.5] TaliPay Customer Service (Location -> Customer)",
        "type": "Story",
        "labels": ["talipay", "phase-1", "service", "must-have"],
        "description": (
            "Sync Olympus Locations to TaliPay Customers.\n\n"
            "TaliPay endpoints: POST /v1/customers, PATCH /v1/customers/{id}, GET /v1/customers/{id}"
        ),
        "acceptance_criteria": [
            "ITaliPayCustomerService: CreateAsync, UpdateAsync, GetAsync.",
            "Field mapping: Location -> TaliPay Customer (name, email, phone, address, payment_term_days, factoring_eligible, advance_rate, discount_fee).",
            "Uses both idempotency layers: event-level (0.1) + API-level (1.3).",
            "Stores ExternalMapping on success.",
            "Logs FinancialAuditEntry (CustomerCreated).",
            "Updates FinancialSummary with TaliPayCustomerId.",
            "Files: Application/Interfaces/ITaliPayCustomerService.cs, Application/DTOs/TaliPay/TaliPayCustomerModels.cs, Infrastructure/Services/TaliPay/TaliPayCustomerService.cs.",
        ],
    },
    {
        "title": "[Phase 1.6] TaliPay Vendor Service (Gygler -> Vendor)",
        "type": "Story",
        "labels": ["talipay", "phase-1", "service", "must-have"],
        "description": (
            "Sync Olympus Gyglers to TaliPay Vendors.\n\n"
            "TaliPay endpoints: POST /v1/vendors, PATCH /v1/vendors/{id}, GET /v1/vendors/{id}"
        ),
        "acceptance_criteria": [
            "ITaliPayVendorService: CreateAsync, UpdateAsync, GetAsync.",
            "Field mapping: Gygler -> TaliPay Vendor (name, email, phone, address, payment_term_days, early_pay_eligible, early_pay_advance_rate, early_pay_discount).",
            "Uses both idempotency layers.",
            "Stores ExternalMapping on success.",
            "Logs FinancialAuditEntry (VendorCreated).",
            "Files: Application/Interfaces/ITaliPayVendorService.cs, Application/DTOs/TaliPay/TaliPayVendorModels.cs, Infrastructure/Services/TaliPay/TaliPayVendorService.cs.",
        ],
    },
    {
        "title": "[Phase 1.7] Location Sync Subscriber (Service Bus)",
        "type": "Story",
        "labels": ["talipay", "phase-1", "function", "must-have"],
        "description": (
            "Syncs Location -> TaliPay Customer on create/update events.\n\n"
            "Trigger: Service Bus — location events topic, talipay-sync subscription."
        ),
        "acceptance_criteria": [
            "FIRST: check EventIdempotencyService (Story 0.1) -> skip if already processed.",
            "On create: TaliPayCustomerService.CreateAsync.",
            "On update: lookup ExternalMapping -> UpdateAsync.",
            "On PAYG setup: UpdateAsync with factoring_eligible=false.",
            "On Factored setup: UpdateAsync with factoring_eligible=true, advance_rate, discount_fee.",
            "Error classification: Transient -> abandon (retry), Validation -> dead-letter.",
            "Mark event as processed on success.",
            "Files: Functions/TaliPay/LocationSyncSubscriber.cs.",
        ],
    },
    {
        "title": "[Phase 1.8] Gygler Sync Subscriber (Service Bus)",
        "type": "Story",
        "labels": ["talipay", "phase-1", "function", "must-have"],
        "description": (
            "Syncs Gygler -> TaliPay Vendor on onboard/update events.\n\n"
            "Trigger: Service Bus — gygler events topic, talipay-sync subscription."
        ),
        "acceptance_criteria": [
            "Event idempotency check (Story 0.1) before any processing.",
            "On onboard: CreateVendorAsync.",
            "On update: lookup ExternalMapping -> UpdateVendorAsync.",
            "Error classification: Transient -> abandon (retry), Validation -> dead-letter.",
            "Mark event as processed on success.",
            "Files: Functions/TaliPay/GyglerSyncSubscriber.cs.",
        ],
    },
    {
        "title": "[Phase 1.9] TaliPay Health Check Function",
        "type": "Story",
        "labels": ["talipay", "phase-1", "function", "must-have"],
        "description": (
            "HTTP function to verify TaliPay connectivity.\n\n"
            "TaliPay endpoint: GET /v1/organizations/{id}"
        ),
        "acceptance_criteria": [
            "GET /api/talipay/health endpoint implemented.",
            "Calls GET /v1/organizations/{id} on TaliPay.",
            "Returns 200 + org name on success.",
            "Returns 503 when TaliPay is unreachable.",
            "Files: Functions/TaliPay/TaliPayHealthCheckFunction.cs.",
        ],
    },

    # ─── PHASE 2: Shift Sync ──────────────────────────────────────────────────
    {
        "title": "[Phase 2.1] PaymentSyncStatus State Machine on GygBase",
        "type": "Story",
        "labels": ["talipay", "phase-2", "data-layer", "must-have"],
        "description": (
            "Lifecycle state tracking for gyg -> payment flow. "
            "Enforces valid state transitions in code and blocks illegal operations."
        ),
        "acceptance_criteria": [
            "New properties on GygBase: PaymentSyncStatus, ShiftSyncedAt, InvoicedAt, InvoicingRunId, ETag.",
            "PaymentSyncStatus enum: NotSynced, ShiftSynced, ShiftSyncFailed, Invoiced, Paid.",
            "State transitions enforced: NotSynced -> ShiftSynced | ShiftSyncFailed; ShiftSyncFailed -> ShiftSynced; ShiftSynced -> Invoiced; Invoiced -> Paid.",
            "Blocking rules: cannot invoice unless ShiftSynced; cannot pay unless Invoiced.",
            "All updates use ETag (Story 0.3).",
            "Files: Domain/Entities/GygBase.cs (modify), Domain/Enums/PaymentSyncStatus.cs, ApplicationDbContext.cs (modify).",
        ],
    },
    {
        "title": "[Phase 2.2] TaliPay Shift Service",
        "type": "Story",
        "labels": ["talipay", "phase-2", "service", "must-have"],
        "description": (
            "Sync approved gygs as pre-rated shifts.\n\n"
            "TaliPay endpoints: POST /v1/shifts, PATCH /v1/shifts/{id}, DELETE /v1/shifts/{id}, "
            "GET /v1/shifts/{id}/calculation, GET /v1/shifts/{id}/shift_line_items"
        ),
        "acceptance_criteria": [
            "ITaliPayShiftService: CreateAsync, UpdateAsync, DeleteAsync, GetCalculationAsync.",
            "Maps: GygBase -> TaliPay Shift (reference_id=gygId, customer_id from mapping, vendor_id from mapping, pre_rated=true, customer_amount, vendor_amount, quantity, measurement_unit, completed_at).",
            "Validates dependencies BEFORE calling TaliPay: customer + vendor ExternalMappings must exist; if not, throw DependencyMissing.",
            "Idempotency key: {gygId}-shift-create-v1.",
            "On success: store ExternalMapping + update PaymentSyncStatus=ShiftSynced + audit log.",
            "On failure: PaymentSyncStatus=ShiftSyncFailed + audit log with error.",
            "Files: Application/Interfaces/ITaliPayShiftService.cs, Application/DTOs/TaliPay/TaliPayShiftModels.cs, Infrastructure/Services/TaliPay/TaliPayShiftService.cs.",
        ],
    },
    {
        "title": "[Phase 2.3] Gyg Shift Sync Subscriber (Service Bus)",
        "type": "Story",
        "labels": ["talipay", "phase-2", "function", "must-have"],
        "description": (
            "Service Bus function that syncs approved gygs to TaliPay as pre-rated shifts.\n\n"
            "Trigger: gyg-events topic, talipay-shift-sync subscription. Filter: GygStatus=Approved."
        ),
        "acceptance_criteria": [
            "Event idempotency check (Story 0.1) before processing.",
            "Calls TaliPayShiftService.CreateAsync.",
            "Transient errors -> abandon (retry).",
            "DependencyMissing (no customer/vendor mapping) -> abandon + create pending-sync record + alert.",
            "Validation errors -> dead-letter.",
            "Files: Functions/TaliPay/GygShiftSyncSubscriber.cs.",
        ],
    },
    {
        "title": "[Phase 2.4] Shift Sync Retry Function (Smart Retry)",
        "type": "Story",
        "labels": ["talipay", "phase-2", "function", "must-have"],
        "description": (
            "Timer function with SMART retry — classifies failure reason before retrying.\n\n"
            "Trigger: every 15 minutes. Queries gygs with PaymentSyncStatus=ShiftSyncFailed."
        ),
        "acceptance_criteria": [
            "Classifies failure reason before retrying: DependencyMissing -> skip, alert if >2h old; Transient -> retry; Validation -> skip permanently, alert.",
            "Max retries configurable (default 10 for transient, 0 for validation).",
            "Exponential backoff between retries: 15m, 30m, 1h, 2h, 4h...",
            "After max retries: alert admin, leave as ShiftSyncFailed.",
            "Audit log all retry attempts.",
            "Files: Functions/TaliPay/ShiftSyncRetryFunction.cs.",
        ],
    },

    # ─── PHASE 3: Invoicing ───────────────────────────────────────────────────
    {
        "title": "[Phase 3.1] Invoicing Run Container & Entity",
        "type": "Story",
        "labels": ["talipay", "phase-3", "data-layer", "must-have"],
        "description": (
            "Track invoicing jobs with distributed locking and progress checkpointing."
        ),
        "acceptance_criteria": [
            "invoicing-runs container created, PK = /runDate.",
            "InvoicingRun entity: Id, RunDate, ClientLocationId, Status, RunType, LockHolder, LockAcquiredAt, LockExpiresAt, TotalGygs, ShiftsSynced, InvoicesCreated, Errors, CustomerInvoiceExternalId, VendorInvoiceExternalIds, ErrorDetails, CutoffStart, CutoffEnd, CutoffTimezone, InvoiceBatchId, CreatedAt, CompletedAt, ETag.",
            "Status enum: Pending, Locked, Preparing, SyncingShifts, CreatingInvoices, Completed, Failed, PartiallyCompleted.",
            "RunType enum: Scheduled, Manual, Retry.",
            "Files: Domain/Entities/InvoicingRun.cs, Domain/Enums/InvoicingRunStatus.cs, Domain/Enums/InvoicingRunType.cs, ApplicationDbContext.cs (modify).",
        ],
    },
    {
        "title": "[Phase 3.2] TaliPay Invoice Service",
        "type": "Story",
        "labels": ["talipay", "phase-3", "service", "must-have"],
        "description": (
            "TaliPay invoice CRUD and supporting operations.\n\n"
            "TaliPay endpoints: POST /v1/invoices, POST /v1/invoices/{id}/add_shifts, "
            "GET /v1/invoices/{id}, GET /v1/invoices/{id}/summary, GET /v1/invoices/{id}/pdf, "
            "GET /v1/invoices/{id}/shift_line_items, PATCH /v1/invoices/{id}, "
            "POST /v1/invoices/{id}/void, DELETE /v1/invoices/{id}, GET /v1/invoices, "
            "GET /v1/invoices/{id}/details"
        ),
        "acceptance_criteria": [
            "ITaliPayInvoiceService: CreateInvoiceAsync, AddShiftsAsync, GetAsync, GetSummaryAsync, GetPdfAsync, ListLineItemsAsync, UpdateAsync, VoidAsync, DeleteAsync, ListAsync.",
            "Idempotency key for create: invoice-{locationId}-{counterPartyType}-{runDate}.",
            "Creates ExternalMapping on success.",
            "Logs FinancialAuditEntry for every operation.",
            "Updates FinancialSummary (TotalInvoicedCents, OutstandingCents).",
            "Files: Application/Interfaces/ITaliPayInvoiceService.cs, Application/DTOs/TaliPay/TaliPayInvoiceModels.cs, Infrastructure/Services/TaliPay/TaliPayInvoiceService.cs.",
        ],
    },
    {
        "title": "[Phase 3.3] Invoicing Timer Function (2am — Atomic Batch)",
        "type": "Story",
        "labels": ["talipay", "phase-3", "function", "must-have"],
        "description": (
            "Timer function with atomic batch preparation to prevent partial invoices.\n\n"
            "Trigger: 0 0 2 * * * (2am daily). "
            "Atomic strategy: Acquire lock -> Prepare -> Validate -> Execute -> Confirm -> Release."
        ),
        "acceptance_criteria": [
            "Acquires distributed lock (InvoicingRun.LockHolder, expires 30 min).",
            "PREPARE PHASE: query all eligible gygs (Approved + ShiftSynced + in cutoff + not invoiced).",
            "VALIDATE PHASE: verify ALL shifts exist in TaliPay. If any shift missing -> sync it or exclude. If validation fails -> abort, log, alert.",
            "Generates InvoiceBatchId and stamps all gygs with it.",
            "EXECUTE PHASE (only after full preparation): create ONE customer invoice (all shift_ids); create vendor invoice(s) grouped by vendor.",
            "CONFIRM PHASE: if customer invoice OK but vendor fails -> void customer invoice -> alert.",
            "Updates gygs: PaymentSyncStatus=Invoiced + InvoicingRunId.",
            "On crash: lock expires -> retry picks up -> InvoiceBatchId prevents duplicate batch.",
            "Files: Functions/TaliPay/InvoicingTimerFunction.cs.",
        ],
    },
    {
        "title": "[Phase 3.4] Manual Invoicing Trigger",
        "type": "Story",
        "labels": ["talipay", "phase-3", "function", "must-have"],
        "description": (
            "HTTP trigger for manual invoicing with the same atomic logic as the timer function.\n\n"
            "POST /api/talipay/invoicing/run — body: { locationId, cutoffStart, cutoffEnd }"
        ),
        "acceptance_criteria": [
            "POST /api/talipay/invoicing/run accepts { locationId, cutoffStart, cutoffEnd }.",
            "Uses same atomic logic as Phase 3.3 with RunType=Manual.",
            "Returns InvoicingRun status in response.",
            "Files: Functions/TaliPay/ManualInvoicingFunction.cs.",
        ],
    },

    # ─── PHASE 4: Credit Notes + Custom Line Items ────────────────────────────
    {
        "title": "[Phase 4.1] TaliPay Credit Note Service",
        "type": "Story",
        "labels": ["talipay", "phase-4", "service", "should-have"],
        "description": (
            "Credit note CRUD + apply/unapply to invoices.\n\n"
            "TaliPay endpoints: POST /v1/credit_notes, PATCH /v1/credit_notes/{id}, "
            "DELETE /v1/credit_notes/{id}, GET /v1/credit_notes/{id}, GET /v1/credit_notes, "
            "POST /v1/invoices/{id}/apply_credit_note, POST /v1/invoices/{id}/unapply_credit_note, "
            "GET /v1/invoices/{id}/credit_note_applications"
        ),
        "acceptance_criteria": [
            "ITaliPayCreditNoteService: CreateAsync, UpdateAsync, DeleteAsync, GetAsync, ListAsync, ApplyAsync, UnapplyAsync, ListApplicationsAsync.",
            "Idempotency on create.",
            "Creates ExternalMapping on success.",
            "Logs FinancialAuditEntry for every operation.",
            "Updates FinancialSummary (TotalCreditNotesCents).",
        ],
    },
    {
        "title": "[Phase 4.2] Custom Line Item Support",
        "type": "Story",
        "labels": ["talipay", "phase-4", "service", "should-have"],
        "description": (
            "Add custom line items to TaliPay invoices.\n\n"
            "TaliPay endpoints: POST /v1/invoices/{id}/custom_line_items, "
            "GET /v1/invoices/{id}/custom_line_items"
        ),
        "acceptance_criteria": [
            "AddCustomLineItemAsync and ListCustomLineItemsAsync added to ITaliPayInvoiceService.",
            "Logs FinancialAuditEntry on create.",
        ],
    },
    {
        "title": "[Phase 4.3] Credit Note Management Functions (HTTP)",
        "type": "Story",
        "labels": ["talipay", "phase-4", "function", "should-have"],
        "description": (
            "HTTP endpoints exposing credit note operations."
        ),
        "acceptance_criteria": [
            "POST /api/talipay/credit-notes — create credit note.",
            "POST /api/talipay/credit-notes/{id}/apply/{invoiceId} — apply to invoice.",
            "POST /api/talipay/credit-notes/{id}/unapply/{invoiceId} — unapply from invoice.",
            "GET /api/talipay/invoices/{id}/credit-notes — list applications.",
            "All operations audit-logged.",
            "Files: Functions/TaliPay/CreditNoteManagementFunction.cs.",
        ],
    },

    # ─── PHASE 5: Payments ────────────────────────────────────────────────────
    {
        "title": "[Phase 5.1] TaliPay Payment Service",
        "type": "Story",
        "labels": ["talipay", "phase-5", "service", "must-have"],
        "description": (
            "Payment reference CRUD + apply/unapply to invoices.\n\n"
            "TaliPay endpoints: POST /v1/payment_references, "
            "POST /v1/invoices/{id}/apply_payment_reference, "
            "POST /v1/invoices/{id}/unapply_payment_reference, "
            "PATCH /v1/payment_references/{id}, DELETE /v1/payment_references/{id}, "
            "GET /v1/payment_references/{id}, GET /v1/payment_references, "
            "GET /v1/invoices/{id}/payment_reference_applications, "
            "GET /v1/payment_reference_applications"
        ),
        "acceptance_criteria": [
            "ITaliPayPaymentService: CreateAsync, UpdateAsync, DeleteAsync, GetAsync, ListAsync, ApplyAsync, UnapplyAsync, ListApplicationsAsync.",
            "Idempotency on create.",
            "Creates ExternalMapping on success.",
            "Logs FinancialAuditEntry for every operation.",
            "Updates FinancialSummary (TotalPaidCents, OutstandingCents).",
        ],
    },
    {
        "title": "[Phase 5.2] PAYG Deposit Debit Function (Service Bus)",
        "type": "Story",
        "labels": ["talipay", "phase-5", "function", "must-have"],
        "description": (
            "Triggered after invoicing completes. For PAYG customers only: "
            "create payment reference -> apply to invoice. Flags shortfall for top-up."
        ),
        "acceptance_criteria": [
            "Triggered after invoicing run completes (Service Bus event).",
            "PAYG customers only — factoring_eligible=false check.",
            "Creates payment reference -> applies to invoice.",
            "If deposit < invoice amount: flags for top-up, alerts finance team.",
            "Updates FinancialSummary.",
            "Files: Functions/TaliPay/PaygDepositDebitFunction.cs.",
        ],
    },
    {
        "title": "[Phase 5.3] Factored Payment Function (HTTP)",
        "type": "Story",
        "labels": ["talipay", "phase-5", "function", "must-have"],
        "description": (
            "HTTP endpoint to record customer payment to factor at terms.\n\n"
            "POST /api/talipay/payments/factored"
        ),
        "acceptance_criteria": [
            "POST /api/talipay/payments/factored records customer payment.",
            "Creates payment reference -> applies to invoice.",
            "Logs FinancialAuditEntry.",
            "Returns updated FinancialSummary.",
            "Files: Functions/TaliPay/FactoredPaymentFunction.cs.",
        ],
    },

    # ─── PHASE 6: Taxes ───────────────────────────────────────────────────────
    {
        "title": "[Phase 6.1] TaliPay Tax Service",
        "type": "Story",
        "labels": ["talipay", "phase-6", "service", "should-have"],
        "description": (
            "Tax configuration CRUD + apply/clear on shift line items.\n\n"
            "TaliPay endpoints: POST /v1/taxes, PATCH /v1/taxes/{id}, DELETE /v1/taxes/{id}, "
            "GET /v1/taxes/{id}, GET /v1/taxes, "
            "POST /v1/shift_line_items/{id}/apply_taxes, POST /v1/shift_line_items/bulk_apply_taxes, "
            "DELETE /v1/shift_line_items/{id}/remove_tax, DELETE /v1/shift_line_items/{id}/clear_taxes, "
            "POST /v1/shift_line_items/bulk_clear_taxes"
        ),
        "acceptance_criteria": [
            "ITaliPayTaxService: CreateAsync, UpdateAsync, DeleteAsync, GetAsync, ListAsync, ApplyAsync, BulkApplyAsync, RemoveAsync, ClearAsync, BulkClearAsync.",
            "Idempotency on create.",
            "Audit log on all operations.",
        ],
    },
    {
        "title": "[Phase 6.2] Tax Management Functions (HTTP)",
        "type": "Story",
        "labels": ["talipay", "phase-6", "function", "should-have"],
        "description": (
            "HTTP endpoints exposing tax CRUD and bulk apply/clear operations."
        ),
        "acceptance_criteria": [
            "POST/GET/PATCH/DELETE /api/talipay/taxes — tax CRUD.",
            "POST /api/talipay/shift-line-items/{id}/taxes — apply tax.",
            "POST /api/talipay/shift-line-items/bulk-apply-taxes — bulk apply.",
            "DELETE /api/talipay/shift-line-items/{id}/taxes — clear taxes.",
            "POST /api/talipay/shift-line-items/bulk-clear-taxes — bulk clear.",
            "Files: Functions/TaliPay/TaxManagementFunction.cs.",
        ],
    },

    # ─── PHASE 7: Webhooks + Event Sync ──────────────────────────────────────
    {
        "title": "[Phase 7.1] Webhook Container & Entity",
        "type": "Story",
        "labels": ["talipay", "phase-7", "data-layer", "must-have"],
        "description": (
            "Cosmos container for incoming TaliPay webhook events with dedup and processing tracking."
        ),
        "acceptance_criteria": [
            "talipay-webhooks container created, PK = /eventType, TTL 30 days.",
            "TaliPayWebhookEvent entity: Id, TaliPayEventId, EventType, Payload, Status (Pending/Processing/Processed/Failed/PendingDependency), AttemptCount, ErrorMessage, ReceivedAt, ProcessedAt, ETag.",
            "Dedup key: TaliPayEventId.",
        ],
    },
    {
        "title": "[Phase 7.2] Webhook Receiver with State Guards",
        "type": "Story",
        "labels": ["talipay", "phase-7", "function", "must-have"],
        "description": (
            "Webhook processor that handles out-of-order delivery and duplicate events.\n\n"
            "POST /api/webhooks/talipay"
        ),
        "acceptance_criteria": [
            "Dedup: check TaliPayEventId -> if Processed, return 200 immediately.",
            "State guard: before applying state change verify current state is expected predecessor (invoice.paid requires PaymentSyncStatus==Invoiced; vendor.paid requires vendor invoice exists; credit_note.applied requires invoice exists).",
            "Deferred processing: if dependency not yet in Olympus, store as PendingDependency, retry on next webhook or timer (every 5 min), max 3 deferred retries then alert.",
            "State transitions: invoice.paid -> PaymentSyncStatus=Paid + update FinancialSummary; invoice.voided -> PaymentSyncStatus=ShiftSynced (rollback); vendor.paid -> update vendor payment status.",
            "Near-real-time reconciliation: after processing verify amount in webhook matches stored amount.",
            "Audit log all webhook events.",
            "Return 200 on success, 500 on error (TaliPay retries on 500).",
            "Files: Functions/TaliPay/TaliPayWebhookFunction.cs.",
        ],
    },
    {
        "title": "[Phase 7.3] Webhook Deferred Processor (Timer)",
        "type": "Story",
        "labels": ["talipay", "phase-7", "function", "must-have"],
        "description": (
            "Timer function to process webhooks deferred due to missing dependencies.\n\n"
            "Trigger: every 5 minutes."
        ),
        "acceptance_criteria": [
            "Queries webhooks with Status=PendingDependency.",
            "Re-checks if dependency now exists in Olympus.",
            "Processes if dependency available, or increments attempt count.",
            "After 3 failed attempts: alert admin, mark as Failed.",
            "Files: Functions/TaliPay/WebhookDeferredProcessorFunction.cs.",
        ],
    },
    {
        "title": "[Phase 7.4] Webhook Management Functions (HTTP)",
        "type": "Story",
        "labels": ["talipay", "phase-7", "function", "must-have"],
        "description": (
            "HTTP endpoints for TaliPay webhook CRUD and event management.\n\n"
            "TaliPay endpoints: POST /v1/webhooks, PATCH /v1/webhooks/{id}, "
            "POST /v1/webhooks/{id}/test, GET /v1/webhooks/events, "
            "GET /v1/webhooks/{id}/delivery_logs, GET /v1/events, "
            "GET /v1/events/{id}, POST /v1/events/{id}/resend"
        ),
        "acceptance_criteria": [
            "POST /api/talipay/webhooks — register webhook endpoint.",
            "PATCH /api/talipay/webhooks/{id} — update webhook.",
            "POST /api/talipay/webhooks/{id}/test — send test event.",
            "GET /api/talipay/webhooks/events — list event types.",
            "GET /api/talipay/webhooks/{id}/delivery-logs — view delivery history.",
            "GET/POST /api/talipay/events — list and resend events.",
            "Files: Functions/TaliPay/WebhookManagementFunction.cs.",
        ],
    },

    # ─── PHASE 8: Vendor Early-Pay ────────────────────────────────────────────
    {
        "title": "[Phase 8.1] Early-Pay Eligibility Check (HTTP)",
        "type": "Story",
        "labels": ["talipay", "phase-8", "function", "nice-to-have"],
        "description": (
            "Returns early-pay eligibility, available advance, and eligible invoices for a Gygler.\n\n"
            "GET /api/talipay/vendors/{gyglerId}/early-pay"
        ),
        "acceptance_criteria": [
            "GET /api/talipay/vendors/{gyglerId}/early-pay returns eligibility status.",
            "Response includes: eligible (bool), available_advance_cents, eligible_invoice_ids.",
            "Checks ExternalMapping for Gygler -> TaliPay Vendor.",
            "Delegates to TaliPay vendor early-pay calculation endpoint.",
        ],
    },
    {
        "title": "[Phase 8.2] Early-Pay Request (HTTP)",
        "type": "Story",
        "labels": ["talipay", "phase-8", "function", "nice-to-have"],
        "description": (
            "Creates a payment reference and applies it to a vendor invoice for early pay.\n\n"
            "POST /api/talipay/vendors/{gyglerId}/early-pay/request"
        ),
        "acceptance_criteria": [
            "POST /api/talipay/vendors/{gyglerId}/early-pay/request processes early-pay.",
            "Creates payment reference -> applies to vendor invoice.",
            "Idempotency on create.",
            "Logs FinancialAuditEntry (EarlyPayRequested).",
            "Returns updated payment status.",
            "Files: Functions/TaliPay/EarlyPayFunction.cs.",
        ],
    },

    # ─── PHASE 9: Attachments + PDF ───────────────────────────────────────────
    {
        "title": "[Phase 9.1] Invoice Attachment & PDF Functions (HTTP)",
        "type": "Story",
        "labels": ["talipay", "phase-9", "function", "nice-to-have"],
        "description": (
            "HTTP endpoints for invoice attachments and PDF retrieval.\n\n"
            "TaliPay endpoints: POST /v1/invoices/{id}/attachments, GET /v1/invoices/{id}/attachments, "
            "DELETE /v1/invoices/{id}/attachments, GET /v1/invoices/{id}/pdf, "
            "GET /v1/invoices/{id}/details"
        ),
        "acceptance_criteria": [
            "POST /api/talipay/invoices/{id}/attachments — upload attachment.",
            "GET /api/talipay/invoices/{id}/attachments — list attachments.",
            "DELETE /api/talipay/invoices/{id}/attachments/{attachmentId} — delete attachment.",
            "GET /api/talipay/invoices/{id}/pdf — stream PDF.",
            "GET /api/talipay/invoices/{id}/details — full invoice details.",
            "Files: Functions/TaliPay/InvoiceAttachmentFunction.cs.",
        ],
    },

    # ─── PHASE 10: Reconciliation + Monitoring ────────────────────────────────
    {
        "title": "[Phase 10.1] Daily Reconciliation Function (6am — Full Scan)",
        "type": "Story",
        "labels": ["talipay", "phase-10", "function", "must-have"],
        "description": (
            "Three-layer daily reconciliation scan for full financial integrity.\n\n"
            "Trigger: 0 0 6 * * * (6am daily).\n\n"
            "Layer 1 — Entity Sync Check: customers + vendors exist in TaliPay.\n"
            "Layer 2 — Shift + Invoice Check: shifts and invoices consistent.\n"
            "Layer 3 — Financial Amount Check: amounts match FinancialSummary.\n\n"
            "TaliPay endpoints: GET /v1/customers, GET /v1/vendors, GET /v1/shifts, "
            "GET /v1/invoices, GET /v1/shift_line_items, GET /v1/customers/{id}, GET /v1/vendors/{id}"
        ),
        "acceptance_criteria": [
            "Layer 1: all Locations with ExternalMapping verified against GET /v1/customers; all Gyglers verified against GET /v1/vendors. Handles pagination (20/page max).",
            "Layer 2: all gygs with ShiftSynced verified in TaliPay; all gygs with Invoiced verified; shift counts per invoice match.",
            "Layer 3: invoice amounts match FinancialSummary; payment totals match; outstanding balance matches.",
            "Mismatches -> financial-audit-log with Action=ReconciliationMismatch.",
            "Critical mismatches (amount mismatch, missing invoice) -> immediate admin alert.",
            "Non-critical mismatches (stale mapping) -> auto-fix + Action=ReconciliationFixed.",
            "Updates FinancialSummary.ReconciliationStatus and LastReconciliationDate.",
            "Files: Functions/TaliPay/ReconciliationTimerFunction.cs.",
        ],
    },
    {
        "title": "[Phase 10.2] Reconciliation Dashboard Functions (HTTP)",
        "type": "Story",
        "labels": ["talipay", "phase-10", "function", "must-have"],
        "description": (
            "HTTP endpoints for reconciliation status, mismatch review, and manual fixes."
        ),
        "acceptance_criteria": [
            "GET /api/talipay/reconciliation/status — summary of last reconciliation run.",
            "GET /api/talipay/reconciliation/mismatches — list all active mismatches.",
            "POST /api/talipay/reconciliation/run — trigger manual reconciliation.",
            "POST /api/talipay/reconciliation/fix/{entityId} — apply auto-fix for specific entity.",
            "Files: Functions/TaliPay/ReconciliationDashboardFunction.cs.",
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
            "labels": story.get("labels", ["talipay", "onboarding-functions"]),
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

    print(f"Creating {len(STORIES)} TaliPay integration stories in project {JIRA_PROJECT_KEY}...")
    print()

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

        # Respect Jira Cloud rate limit (~10 req/s)
        if i < len(STORIES):
            time.sleep(0.15)

    print()
    if failed:
        print(f"{len(failed)} story/stories failed to create:", file=sys.stderr)
        for title in failed:
            print(f"  - {title}", file=sys.stderr)
        sys.exit(1)

    print(f"All {len(STORIES)} stories created successfully.")


if __name__ == "__main__":
    main()
