"""Reads customer_records.json and places outbound Vapi calls.

Safety: every call goes to TEST_PHONE_OVERRIDE unless --live is passed AND
the target number is in ALLOWLISTED_NUMBERS. This prevents accidentally
dialing the fictional numbers in customer_records.json.
"""
import argparse
import json
import os
from pathlib import Path

import httpx

VAPI_API_KEY = os.environ["VAPI_API_KEY"]
VAPI_ASSISTANT_ID = os.environ["VAPI_ASSISTANT_ID"]
VAPI_PHONE_NUMBER_ID = os.environ["VAPI_PHONE_NUMBER_ID"]  # Vapi-provisioned outbound number
TEST_PHONE_OVERRIDE = os.environ.get("TEST_PHONE_OVERRIDE")
ALLOWLISTED_NUMBERS = set(os.environ.get("ALLOWLISTED_NUMBERS", "").split(","))

RECORDS_PATH = Path(__file__).parent / "customer_records.json"


def place_call(record: dict, live: bool) -> dict:
    target = record["phone"]
    if not live or target not in ALLOWLISTED_NUMBERS:
        if not TEST_PHONE_OVERRIDE:
            raise RuntimeError("TEST_PHONE_OVERRIDE not set — refusing to dial a fictional number")
        target = TEST_PHONE_OVERRIDE

    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,
        "customer": {"number": target},
        "assistantOverrides": {
            "variableValues": {
                "name": record["name"],
                "amount": record["amount"],
                "currency": record["currency"],
                "plan": record["plan"],
                "failure_reason": record["failure_reason"],
            }
        },
        "metadata": {"customer_id": record["customer_id"]},
    }
    resp = httpx.post(
        "https://api.vapi.ai/call",
        headers={"Authorization": f"Bearer {VAPI_API_KEY}"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="allow dialing allowlisted real numbers")
    parser.add_argument("--limit", type=int, default=None, help="only call first N records")
    args = parser.parse_args()

    records = json.loads(RECORDS_PATH.read_text())
    if args.limit:
        records = records[: args.limit]

    for record in records:
        result = place_call(record, live=args.live)
        print(f"{record['customer_id']}: call queued -> {result.get('id')}")


if __name__ == "__main__":
    main()
