# Sanctions Screening — Insertion Point & Design

## 1. Pipeline Position

Live pipeline retrieved via `get_compliance_pipeline` (banking-api MCP):

```
kyc_check → aml_analysis → [NEW: sanctions_screening] → approval
```

**Rationale:** Sanctions screening must run *after* AML analysis (which flags suspicious
activity patterns) and *before* approval (the final compliance gate). Inserting
between steps 2 and 3 ensures the compliance officer's approval decision already
incorporates the OFAC/UN match result. Running earlier (before AML) would mean
approving transactions with unknown AML risk; running at approval would collapse
two logically distinct checks into one job.

Current pipeline (from MCP):

| Step | Name | Description |
|------|------|-------------|
| 1 | `kyc_check` | Verify customer identity |
| 2 | `aml_analysis` | Anti-money laundering screening |
| **3 (new)** | **`sanctions_screening`** | **Real-time OFAC/UN sanctions check** |
| 4 (was 3) | `approval` | Final compliance approval |

## 2. Data Inputs Required

| Field | Type | Source | Notes |
|---|---|---|---|
| `customer_id` | string | Transaction payload | Existing customer record; used for watchlist name-match |
| `counterparty_details` | dict | Transaction payload | `name` (required), `country`, `account` (optional) |
| `transaction_amount` | float | Transaction payload | Used for risk-weighting confidence score; not used in match logic directly |

**Sample transaction shape** (consistent with AML module output):

```json
{
  "customer_id": "CUST-0042",
  "counterparty_details": {
    "name": "Acme Trading LLC",
    "country": "US",
    "account": "IBAN-XX-001"
  },
  "transaction_amount": 25000.00
}
```

## 3. Output Schema

```json
{
  "screened": true,
  "match_list": [
    {
      "list_source": "OFAC",
      "matched_name": "Acme Trading LLC",
      "score": 0.97
    }
  ],
  "confidence": 0.97
}
```

| Field | Type | Description |
|-------|------|-------------|
| `screened` | bool | `true` if screening executed successfully; `false` on API failure |
| `match_list` | list | Zero or more matches; each entry has `list_source`, `matched_name`, `score` (0–1) |
| `confidence` | float (0–1) | Highest match score across all lists; `0.0` when `match_list` is empty |

## 4. Integration Contract with the AML Module

- **Input from AML module:** `aml_result` dict (`status`, `risk_score`) is passed through
  unchanged to the approval step; sanctions screening operates independently of the AML verdict.
- **Output to Approval step:** any non-empty `match_list` with `confidence >= 0.75` is a
  hard stop — the transaction is automatically routed to manual compliance review and cannot
  be auto-approved.
- **Failure mode:** if the sanctions API is unreachable or returns an unexpected error,
  `screened` MUST be `false` and the transaction MUST be routed to manual review.
  Silent pass-through on API failure is a PCI DSS Req 6 violation.
- **PCI DSS notes:**
  - `customer_id` and `counterparty_details.name` must not appear in application logs
    in plaintext (PCI DSS Req 3).
  - Screening results containing customer PII must be stored encrypted (PCI DSS Req 3/4).
  - All screening calls must be audit-logged to `audit_log/` (PCI DSS Req 10).

## 5. Open Questions / Risks

| Risk | Mitigation |
|------|-----------|
| False-positive rate on name matching | Use fuzzy score threshold 0.75; route borderline matches (0.5–0.75) to manual review |
| OFAC vs UN list precedence | Take the maximum `score` across both lists as `confidence` |
| List refresh cadence | Lists are stubbed deterministically in the lab; production should refresh daily |
| Multi-language / transliterated names | Out of scope for this lab (stub only) |
