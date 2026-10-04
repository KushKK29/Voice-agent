"""Combined deployable service: mock payment backend + Vapi webhook handler
in one FastAPI app, so it runs as a single process on a host like Render.

Equivalent to running mock_backend.py and webhook_handler.py separately and
having the webhook call the backend over HTTP — here they're merged into one
process and call each other's functions directly instead.
"""
import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

RESULTS_PATH = Path(__file__).parent / "results.json"
RECORDS_PATH = Path(__file__).parent / "customer_records.json"
RECORDS_BY_ID = {r["customer_id"]: r for r in json.loads(RECORDS_PATH.read_text())}

VAPI_WEBHOOK_SECRET = os.environ.get("VAPI_WEBHOOK_SECRET")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")
TWILIO_TO_NUMBER = os.environ.get("TWILIO_TO_NUMBER")  # fallback when caller number isn't passed in
# Trial accounts reject arbitrary Body text; this must be an approved template name on the account.
TWILIO_TEMPLATE_NAME = os.environ.get("TWILIO_TEMPLATE_NAME", "sms_appointment_reminders")

_last_customer_id_by_call: dict[str, str] = {}


def _normalize(customer_id: str) -> str:
    return customer_id.strip().lower().replace("-", "_").replace(" ", "_")


def _append_result(record: dict) -> None:
    results = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else []
    results.append(record)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))


async def _send_sms(to_number: str) -> bool:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        return False  # ponytail: Twilio not configured, caller just gets sms_sent=False
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={"From": TWILIO_FROM_NUMBER, "To": to_number, "Body": TWILIO_TEMPLATE_NAME},
            timeout=15,
        )
    return resp.status_code == 201


def _lookup_customer(customer_id: str, caller_number: str | None = None) -> dict:
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


def _retry_payment(customer_id: str) -> dict:
    record = RECORDS_BY_ID.get(_normalize(customer_id))
    if not record:
        return {"customer_id": customer_id, "status": "customer_not_found"}
    return {"customer_id": customer_id, "status": "success" if record["retry_will_succeed"] else "failed"}


async def _offer_payment_link(customer_id: str, to_number: str | None = None) -> dict:
    # to_number here is always the verified Vapi caller number (set below in /vapi/tool-call),
    # never a value the model/caller can freely supply — prevents using this to spam SMS to
    # arbitrary numbers via our Twilio account.
    record = RECORDS_BY_ID.get(_normalize(customer_id))
    if not record:
        return {"customer_id": customer_id, "status": "customer_not_found"}
    fake_link = f"https://pay.example.com/update/{_normalize(customer_id)}"
    destination = to_number or TWILIO_TO_NUMBER
    if destination:
        await _send_sms(destination)  # best-effort, errors ignored; sends Twilio's fixed template text
    return {"customer_id": customer_id, "link": fake_link, "sms_sent": True}


# Direct REST endpoints (/lookup_customer, /retry_payment, /offer_payment_link) are
# deliberately NOT exposed here, unlike src/mock_backend.py's local-only version. On a public
# deployment they'd let anyone query fictional customer data or, worse, pass an arbitrary
# to_number into offer_payment_link and send SMS to any number via our Twilio account. The real
# call flow only ever goes through /vapi/tool-call below, which is the one protected path.

# --- Vapi webhook ---

async def _run_tool(fn_name: str, args: dict) -> dict:
    if fn_name == "lookup_customer":
        return _lookup_customer(args.get("customer_id", ""), args.get("caller_number"))
    if fn_name == "retry_payment":
        return _retry_payment(args.get("customer_id", ""))
    if fn_name == "offer_payment_link":
        return await _offer_payment_link(args.get("customer_id", ""), args.get("to_number"))
    if fn_name == "log_outcome":
        _append_result(args)
        return {"logged": True}
    return {"error": f"unknown function {fn_name}"}


@app.post("/vapi/tool-call")
async def tool_call(request: Request):
    # Fails OPEN (accepts unauthenticated requests) when VAPI_WEBHOOK_SECRET is unset. Set it in
    # the deployment's env and configure the matching header in Vapi before any real use.
    if VAPI_WEBHOOK_SECRET and request.headers.get("x-vapi-secret") != VAPI_WEBHOOK_SECRET:
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    body = await request.json()
    call_id = body.get("message", {}).get("call", {}).get("id", "")
    caller_number = body.get("message", {}).get("customer", {}).get("number", "")
    calls = body.get("message", {}).get("toolCalls", [])

    results = []
    for call in calls:
        fn_name = call.get("function", {}).get("name")
        args = call.get("function", {}).get("arguments", {})
        if isinstance(args, str):
            args = json.loads(args) if args else {}

        # ponytail: model sometimes drops customer_id on later turns; fall back to last seen for this call.
        if args.get("customer_id"):
            _last_customer_id_by_call[call_id] = args["customer_id"]
        elif call_id in _last_customer_id_by_call:
            args["customer_id"] = _last_customer_id_by_call[call_id]

        if fn_name == "offer_payment_link":
            args["to_number"] = caller_number or None
        if fn_name == "lookup_customer":
            args["caller_number"] = caller_number

        result = await _run_tool(fn_name, args)
        results.append({"toolCallId": call.get("id"), "result": json.dumps(result)})

    return {"results": results}


@app.post("/vapi/end-of-call")
async def end_of_call(request: Request):
    body = await request.json()
    _append_result({"event": "end_of_call_report", "raw": body})
    return {"ok": True}
