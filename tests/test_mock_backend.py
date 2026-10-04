"""Smallest check that survives a logic break. No framework fixtures needed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mock_backend import _normalize, lookup_customer, retry_payment, offer_payment_link


def test_normalize_handles_casing_and_separators():
    assert _normalize("CUST_001") == _normalize("cust-001") == _normalize("Cust 001")


def test_lookup_customer_found():
    result = lookup_customer("cust_003")
    assert result["found"] is True
    assert result["name"] == "Meera Iyer"
    assert result["phone_verified"] is False  # no caller_number passed


def test_lookup_customer_phone_verified_on_match():
    result = lookup_customer("cust_003", caller_number="+91TESTNUM03")
    assert result["phone_verified"] is True


def test_lookup_customer_not_found():
    assert lookup_customer("cust_999")["found"] is False


def test_retry_payment_matches_record():
    assert retry_payment("cust_003")["status"] == "success"   # retry_will_succeed: true
    assert retry_payment("CUST_001")["status"] == "failed"    # retry_will_succeed: false, casing variant


def test_retry_payment_unknown_customer_not_found():
    assert retry_payment("cust_999")["status"] == "customer_not_found"


def test_offer_payment_link_shape():
    result = offer_payment_link("cust_002")
    assert result["link"].startswith("https://")
    assert result["sms_sent"] is True  # demo always reports success; Twilio send is best-effort


def test_offer_payment_link_unknown_customer_not_found():
    assert offer_payment_link("cust_999")["status"] == "customer_not_found"


if __name__ == "__main__":
    test_normalize_handles_casing_and_separators()
    test_lookup_customer_found()
    test_lookup_customer_phone_verified_on_match()
    test_lookup_customer_not_found()
    test_retry_payment_matches_record()
    test_retry_payment_unknown_customer_not_found()
    test_offer_payment_link_shape()
    test_offer_payment_link_unknown_customer_not_found()
    print("all checks passed")
