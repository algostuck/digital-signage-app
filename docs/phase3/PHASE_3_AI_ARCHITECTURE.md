# Phase 3 — AI Architecture

Principle: AI is an **optional, policy-governed, adapter-isolated** layer.
Core CMS/publishing must be fully functional with every AI flag off
(NFR3-06). No AI logic in controllers; all of it lives in `app/services/ai/`.

## 1. Provider adapter (the LocalStorage pattern, again)

```
AIProvider (interface)
 ├── generate_text(policy, template, inputs) -> AIResult
 ├── generate_creative(policy, dimensions, inputs) -> AIResult
 └── localize(policy, content, target_locale) -> AIResult

AIResult = {content, confidence, model_ref, provider, template_version}
```

- `LocalDeterministicProvider` (default in dev/test): rule/template-based
  transforms (casing, truncation to dimension, placeholder-preserving
  locale substitution from packaged glossaries). Fully deterministic —
  tests never depend on an external model.
- Real providers (OpenAI/Anthropic/Azure/on-prem) are config swaps
  (`AI_PROVIDER`, credentials via env/secret store). Timeouts + retries +
  circuit-break to fallback; provider calls only from Celery or with strict
  request-path budgets on explicitly interactive endpoints.

## 2. Governance (P3-AI-004/005)

Every operation writes:
```
ai_requests: org, actor, operation, provider, model_ref,
             template_version, status, created_at
ai_outputs:  request_id, output_kind (text|creative|localization),
             content_json or asset/template ref, confidence,
             safety_status (pending|passed|flagged), approved_by, revision
```
- Never stored: provider secrets, raw API keys, or prompt content that
  embeds credentials. Template *versions* are recorded; templates live in
  code/config.
- `ai_policies` per tenant: allowed operations, brand guardrails
  (banned terms, tone rules for the local provider; forwarded as
  constraints to real providers), approval routing.

## 3. Approval integration (reuse 2A)
`ai_output` registers as an approval-engine entity adapter: when the tenant
policy requires it, generated outputs enter the same inbox, maker-checker
rules, action trail and notifications as campaigns/templates. Approved
creative outputs materialize as normal draft assets/templates.

## 4. Explainability & UI honesty (master-prompt STEP 27)
The AI Studio labels every element as Fact / Recommendation / Prediction /
Automated action, and displays confidence, model version, input scope and
last-updated. Low-confidence results are visually demoted and default to
the deterministic path.

## 5. Fleet "AI" (P3-M07) — deterministic first
Anomaly detection starts as explainable statistics over existing telemetry
(rolling baselines, threshold windows, repeated-failure counts) with
`evidence_json` pointing at the exact heartbeats/events/incidents behind a
score. A model-based scorer can plug in behind the same interface later;
recommendations always carry evidence rows and never auto-execute
destructive actions (P3-OPS-003).

## 6. Cost control (STEP 39)
`ai_requests` doubles as the usage ledger (per-tenant counts by operation/
provider); quotas can extend 2K's quota engine (`max_ai_requests_per_day`)
when a paid provider is configured. Beat-driven AI work is bounded per run.

## 7. Failure ladder
```
provider ok → use result (tagged, versioned)
low confidence → deterministic rules result, marked as fallback
provider down/timeout → deterministic result + provider incident notification
flag off → AI surfaces absent; everything else unchanged
```
