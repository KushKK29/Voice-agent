# Autopay Recovery Voice Agent (Vapi)

Demo voice agent. Calls customers with failed autopay payments, offers retry or
payment-method update. Built on Vapi. See [PLAN.md](PLAN.md) for architecture.

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in VAPI_API_KEY etc. Get these from vapi.ai dashboard.
```

Create the Vapi assistant from `src/assistant_config.json` (via Vapi dashboard
or `POST https://api.vapi.ai/assistant` with that JSON body) and put the
returned id into `VAPI_ASSISTANT_ID`.

Expose the webhook locally:
```bash
ngrok http 8000
# copy the https URL into WEBHOOK_BASE_URL in .env, and into
# assistant_config.json's serverUrl before creating the assistant
```

## Run
Terminal 1 — mock payment backend:
```bash
uvicorn src.mock_backend:app --port 8001
```

Terminal 2 — webhook handler (receives Vapi tool-calls):
```bash
uvicorn src.webhook_handler:app --port 8000
```

This demo runs inbound (see PLAN.md "Call direction note" — Vapi trial numbers
can't dial out without an imported Twilio number). Call the Vapi phone number
shown in the dashboard yourself, and when asked, give one of the customer IDs
from `src/customer_records.json` (e.g. "cust_001") to role-play that customer.

Results land in `src/results.json`.

`src/trigger_calls.py` is kept for the outbound path (production would use
it once a verified outbound number is set up) but isn't used for this demo.

## Tests
```bash
python tests/test_mock_backend.py
```

## Safety
- All 10 customer records are fictional. `trigger_calls.py` refuses to dial
  any number that isn't `TEST_PHONE_OVERRIDE` unless `--live` is passed AND
  the number is in `ALLOWLISTED_NUMBERS` — set this to a number you own.
- No card number, CVV, or OTP is ever requested or accepted by the agent.
- Set `VAPI_WEBHOOK_SECRET` in `.env` and configure the matching header in
  Vapi's assistant/server settings to require authentication on the webhook
  endpoint — see "Security" in [PLAN.md](PLAN.md) for why this matters and
  what's still a known gap (identity verification) in this demo.

## Limitations
See "Limitations & long-term fix" and "Security" in [PLAN.md](PLAN.md).
