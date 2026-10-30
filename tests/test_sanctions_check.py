"""
Test suite for sanctions_check.py — covers the five required cases.

Data model under test:
  screen_transaction(customer_id, counterparty_details, transaction_amount)
  -> {"screened": bool, "match_list": [{"list_source", "matched_name", "score"}], "confidence": float}

All sanctions API calls are mocked so the suite is fully deterministic.
"""

import time
from unittest.mock import patch

import pytest

from sanctions_check import SanctionsMatch, screen_transaction

VALID_CUSTOMER_ID = "CUST-00123"
VALID_COUNTERPARTY = {"name": "Acme Trading Ltd", "country": "US"}
VALID_AMOUNT = 5000.00


# ---------------------------------------------------------------------------
# Case 1: clean transaction — no matches
# ---------------------------------------------------------------------------

def test_clean_transaction_passes_with_no_matches():
    with patch("sanctions_check._query_sanctions_lists", return_value=[]):
        result = screen_transaction(VALID_CUSTOMER_ID, VALID_COUNTERPARTY, VALID_AMOUNT)
    assert result["screened"] is True
    assert result["match_list"] == []
    assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Case 2: OFAC match detection
# ---------------------------------------------------------------------------

def test_ofac_match_is_detected():
    mock_match = SanctionsMatch(list_source="OFAC", matched_name="Acme Trading Ltd", score=0.91)
    with patch("sanctions_check._query_sanctions_lists", return_value=[mock_match]):
        result = screen_transaction(VALID_CUSTOMER_ID, VALID_COUNTERPARTY, VALID_AMOUNT)
    assert result["screened"] is True
    assert len(result["match_list"]) == 1
    assert result["match_list"][0]["list_source"] == "OFAC"
    assert result["match_list"][0]["score"] == pytest.approx(0.91)
    assert result["confidence"] == pytest.approx(0.91)


# ---------------------------------------------------------------------------
# Case 3: UN list match detection
# ---------------------------------------------------------------------------

def test_un_list_match_is_detected():
    mock_match = SanctionsMatch(list_source="UN", matched_name="Acme Trading Ltd", score=0.83)
    with patch("sanctions_check._query_sanctions_lists", return_value=[mock_match]):
        result = screen_transaction(VALID_CUSTOMER_ID, VALID_COUNTERPARTY, VALID_AMOUNT)
    assert result["screened"] is True
    assert len(result["match_list"]) == 1
    assert result["match_list"][0]["list_source"] == "UN"
    assert result["match_list"][0]["score"] == pytest.approx(0.83)
    assert result["confidence"] == pytest.approx(0.83)


def test_dual_list_match_confidence_is_max_score():
    """When both OFAC and UN match, confidence should be the highest score."""
    ofac_match = SanctionsMatch(list_source="OFAC", matched_name="Acme Trading Ltd", score=0.91)
    un_match = SanctionsMatch(list_source="UN", matched_name="Acme Trading Ltd", score=0.83)
    with patch("sanctions_check._query_sanctions_lists", return_value=[ofac_match, un_match]):
        result = screen_transaction(VALID_CUSTOMER_ID, VALID_COUNTERPARTY, VALID_AMOUNT)
    assert result["screened"] is True
    assert len(result["match_list"]) == 2
    assert result["confidence"] == pytest.approx(0.91)


# ---------------------------------------------------------------------------
# Case 4: malformed input handling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "customer_id, counterparty, amount",
    [
        ("", VALID_COUNTERPARTY, VALID_AMOUNT),               # empty customer_id
        (VALID_CUSTOMER_ID, {}, VALID_AMOUNT),                # missing 'name' key
        (VALID_CUSTOMER_ID, VALID_COUNTERPARTY, -100.0),      # negative amount
        (None, VALID_COUNTERPARTY, VALID_AMOUNT),             # None customer_id
        (VALID_CUSTOMER_ID, "not-a-dict", VALID_AMOUNT),      # wrong type for counterparty
    ],
)
def test_malformed_input_is_rejected_gracefully(customer_id, counterparty, amount):
    result = screen_transaction(customer_id, counterparty, amount)
    assert result["screened"] is False
    assert result["match_list"] == []
    assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Case 5: performance / latency assertion (< 200 ms on mock)
# ---------------------------------------------------------------------------

MOCK_API_LATENCY_BUDGET_MS = 200


def test_screening_latency_within_budget():
    with patch("sanctions_check._query_sanctions_lists", return_value=[]):
        start = time.monotonic()
        screen_transaction(VALID_CUSTOMER_ID, VALID_COUNTERPARTY, VALID_AMOUNT)
        elapsed_ms = (time.monotonic() - start) * 1000
    assert elapsed_ms < MOCK_API_LATENCY_BUDGET_MS, (
        f"Screening took {elapsed_ms:.1f}ms, exceeds {MOCK_API_LATENCY_BUDGET_MS}ms budget"
    )
