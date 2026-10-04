"""Receives Vapi tool-calls during a live call, and end-of-call reports.
Logs every outcome to results.json for human audit."""
import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
RESULTS_PATH = Path(__file__).parent / "results.json"
BACKEND_URL = os.environ.get("MOCK_BACKEND_URL", "http://localhost:8001")
VAPI_WEBHOOK_SECRET = os.environ.get("VAPI_WEBHOOK_SECRET")
_last_customer_id_by_call: dict[str, str] = {}


def _append_result(record: dict) -> None:
    results = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else []
    results.append(record)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))


async def _run_tool(fn_name: str, args: dict, client: httpx.AsyncClient) -> dict:
    if fn_name == "lookup_customer":
        resp = await client.post(f"{BACKEND_URL}/lookup_customer", params=args)
        return resp.json()
    if fn_name == "retry_payment":
        resp = await client.post(f"{BACKEND_URL}/retry_payment", params=args)
        return resp.json()
    if fn_name == "offer_payment_link":
        resp = await client.post(f"{BACKEND_URL}/offer_payment_link", params=args)
        return resp.json()
    if fn_name == "log_outcome":
        _append_result(args)
        return {"logged": True}
    return {"error": f"unknown function {fn_name}"}


@app.post("/vapi/tool-call")
async def tool_call(request: Request):
    # Fails OPEN (accepts unauthenticated requests) when VAPI_WEBHOOK_SECRET is unset — true in
    # this submitted demo, since Vapi's dashboard wasn't reconfigured to send the header after
    # this check was added. Set VAPI_WEBHOOK_SECRET and the matching Vapi header before any real
    # deployment; see PLAN.md Security section.
    if VAPI_WEBHOOK_SECRET and request.headers.get("x-vapi-secret") != VAPI_WEBHOOK_SECRET:
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    body = await request.json()
    call_id = body.get("message", {}).get("call", {}).get("id", "")
    caller_number = body.get("message", {}).get("customer", {}).get("number", "")
    calls = body.get("message", {}).get("toolCalls", [])

    results = []
    async with httpx.AsyncClient() as client:
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
                # Never trust a model-supplied destination — always the verified caller's own number, or none.
                args["to_number"] = caller_number or None
            if fn_name == "lookup_customer":
                args["caller_number"] = caller_number

            result = await _run_tool(fn_name, args, client)
            results.append({"toolCallId": call.get("id"), "result": json.dumps(result)})

    return {"results": results}


@app.post("/vapi/end-of-call")
async def end_of_call(request: Request):
    body = await request.json()
    _append_result({"event": "end_of_call_report", "raw": body})
    return {"ok": True}
