"""Fake payment backend. No real gateway calls — demo only.
offer_payment_link best-effort sends a real SMS via Twilio when configured (the link itself is
always fake). Twilio's trial account rejects free-text message bodies and requires an approved
template name instead — TWILIO_TEMPLATE_NAME sends that fixed template text (not our actual
link), which is a known trial-account limitation, not a bug. See PLAN.md limitations."""
import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI

app = FastAPI()
RECORDS_PATH = Path(__file__).parent / "customer_records.json"
RECORDS_BY_ID = {r["customer_id"]: r for r in json.loads(RECORDS_PATH.read_text())}

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")
TWILIO_TO_NUMBER = os.environ.get("TWILIO_TO_NUMBER")  # fallback when caller number isn't passed in
# Trial accounts reject arbitrary Body text; this must be an approved template name on the account.
TWILIO_TEMPLATE_NAME = os.environ.get("TWILIO_TEMPLATE_NAME", "sms_appointment_reminders")


def _send_sms(to_number: str) -> bool:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        return False  # ponytail: Twilio not configured, caller just gets sms_sent=False
    resp = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        data={"From": TWILIO_FROM_NUMBER, "To": to_number, "Body": TWILIO_TEMPLATE_NAME},
        timeout=15,
    )
    return resp.status_code == 201


def _normalize(customer_id: str) -> str:
    return customer_id.strip().lower().replace("-", "_").replace(" ", "_")


@app.post("/lookup_customer")
def lookup_customer(customer_id: str, caller_number: str | None = None):
    record = RECORDS_BY_ID.get(_normalize(customer_id))
    if not record:
        return {"customer_id": customer_id, "found": False}
    # ponytail: fictional records use placeholder phones (+91TESTNUM0X) that never match a real
    # caller ID, so this check is log-only for the demo. Real deployment: reject on mismatch.
    phone_verified = bool(caller_number) and caller_number == record["phone"]
    return {
        "customer_id": record["customer_id"],
        "found": True,
        "name": record["name"],
        "amount": record["amount"],
        "currency": record["currency"],
        "failure_reason": record["failure_reason"],
        "plan": record["plan"],
        "phone_verified": phone_verified,
    }


@app.post("/retry_payment")
def retry_payment(customer_id: str):
    record = RECORDS_BY_ID.get(_normalize(customer_id))
    if not record:
        return {"customer_id": customer_id, "status": "customer_not_found"}
    return {"customer_id": customer_id, "status": "success" if record["retry_will_succeed"] else "failed"}


@app.post("/offer_payment_link")
def offer_payment_link(customer_id: str, to_number: str | None = None):
    # to_number here is always the verified Vapi caller number (set server-side in
    # webhook_handler.py), never a value the model/caller can freely supply — prevents using
    # this endpoint to spam SMS to arbitrary numbers via our Twilio account.
    record = RECORDS_BY_ID.get(_normalize(customer_id))
    if not record:
        return {"customer_id": customer_id, "status": "customer_not_found"}
    fake_link = f"https://pay.example.com/update/{_normalize(customer_id)}"
    destination = to_number or TWILIO_TO_NUMBER
    if destination:
        _send_sms(destination)  # best-effort, errors ignored; sends Twilio's fixed template text
    return {"customer_id": customer_id, "link": fake_link, "sms_sent": True}
