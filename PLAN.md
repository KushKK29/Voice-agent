# Voice Agent for Autopay Recovery — Implementation Plan

## Goal
Vapi-based voice agent for autopay recovery: confirms caller identity, explains the failure reason, offers to retry payment or update payment method, and logs outcome. Demo only: 10 fictional customer records, operator calls the agent's number themselves to role-play one of those customers (inbound demo — see "Call direction" note below).

## Call direction note
Vapi's free trial numbers are inbound-only for new accounts; true outbound dialing needs an imported Twilio/Vonage number tied to a paid or verified-caller setup. For this assignment, the demo runs **inbound**: the operator calls the Vapi-assigned number and the agent asks for a customer ID to identify them, then proceeds through the same recovery flow a real outbound call would follow. Production would flip this to outbound via `trigger_calls.py` once a verified outbound-capable number is available — code for that path is kept in `src/trigger_calls.py` for reference, but isn't used in the submitted demo.

## Stack
- **Vapi** (vapi.ai) — telephony + STT/TTS + LLM orchestration, outbound call API. LLM: OpenAI GPT-4.1 (Vapi's built-in default) — tried Google Gemini first but its Vapi integration returned a mid-call pipeline error during testing, so switched to the stable default.
- **Python** for the trigger script, mock payment backend, webhook receiver (FastAPI).
- **ngrok** (or Vapi's own tunnel) to expose local webhook during dev.
- No new DB — JSON file as mock "payments" store. (ponytail: flat file, upgrade to real DB if this becomes a real service.)

## Architecture
```
customer_records.json (10 fictional records: name, phone, amount, failure_reason)
        │
        ▼
trigger_calls.py ──POST──▶ Vapi /call API (assistant config inline or assistantId)
                                   │
                         Vapi runs call: STT → LLM (system prompt) → TTS
                                   │
                         Tool calls back to our webhook ──▶ FastAPI app
                                   │                         - retry_payment(customer_id)
                                   │                         - update_payment_method(customer_id)
                                   ▼
                         call ends → Vapi sends end-of-call-report webhook
                                   │
                                   ▼
                         webhook_handler.py logs outcome to results.json
```

## Assistant design (Vapi assistant config)
- **First message**: "Hi, this is Razorpay calling about a recent payment issue on your account. Am I speaking with {{name}}?"
- **System prompt**: identity confirmation → state failure reason (e.g., insufficient funds, card expired, bank declined) → ask customer to choose: (a) retry now, (b) update card, (c) call back later → confirm action → polite close.
- **Guardrails**:
  - Never ask for full card number, CVV, or OTP over voice (hard rule in system prompt + Vapi content filters).
  - Max call duration 3 min (Vapi `maxDurationSeconds`).
  - If customer says "wrong number" or denies identity → apologize, end call, mark `wrong_contact`.
  - If customer sounds distressed/hostile → escalate: offer human callback, end call.
- **Tools exposed to the LLM** (Vapi function-calling):
  - `retry_payment(customer_id)` → calls our mock backend, returns success/fail.
  - `lookup_customer(customer_id)` → verifies identity and returns account details before any payment talk.
  - `offer_payment_link(customer_id)` → returns a fake update-card link and sends a **real SMS** via Twilio to the verified caller's number. Twilio's trial account rejects arbitrary free-text message bodies and only accepts a pre-approved template name as the `Body` value, so the delivered SMS is Twilio's fixed template text (e.g. an appointment-reminder template), not our actual link copy — a trial-account restriction, not a code limitation. Configurable via `TWILIO_TEMPLATE_NAME` in `.env`. The link itself stays fake regardless (no real payment gateway).
  - `log_outcome(customer_id, outcome, notes)` → always called at end of call.

## Files
```
voice-agent/
  PLAN.md
  README.md
  requirements.txt
  .env.example
  src/
    customer_records.json       # 10 fictional records
    assistant_config.json       # Vapi assistant definition (system prompt, tools, voice)
    trigger_calls.py            # reads records, POSTs to Vapi /call for each
    mock_backend.py             # FastAPI: fake payment retry + link generation
    webhook_handler.py          # FastAPI: receives Vapi tool-calls + end-of-call report
    results.json                # output log (created at runtime)
  tests/
    test_mock_backend.py        # asserts retry logic / success-rate simulation
```

## Guardrails / human review
- All 10 records fictional, phone numbers default to the operator's own test number (overridable via `TEST_PHONE_OVERRIDE` env var) so no real customer is ever dialed.
- Real outbound call only fires when `--live` flag passed AND number is in an explicit allowlist in `.env`.
- Every call outcome logged with transcript reference (Vapi provides transcript + recording URL) for human audit.
- No OTP/card data collection — enforced in system prompt and by never exposing a tool that accepts raw card data.

## Evaluation
- `tests/test_mock_backend.py`: asserts retry endpoint returns success/fail deterministically per seeded customer_id, and link generation returns well-formed fake URL.
- Manual: one live test call to operator's own number, verify transcript + webhook log round-trip, attach recording/transcript link in submission.

## Security
- **Webhook authentication**: `webhook_handler.py` checks an `x-vapi-secret` header against `VAPI_WEBHOOK_SECRET` (set in `.env`) before processing any tool-call, rejecting with 401 otherwise. Currently unset in the submitted demo (Vapi dashboard wasn't reconfigured to send the header after adding this, to avoid another live-call credit spend) — **production must set this** so the public ngrok/webhook URL can't be driven by arbitrary POSTs.
- **SMS destination**: `offer_payment_link`'s `to_number` is set server-side in `webhook_handler.py` from Vapi's verified `message.customer.number` field, never taken from model/tool-call arguments — prevents using the endpoint to send SMS to arbitrary numbers through our Twilio account.
- **Identity verification is weak by design in this demo**: the only "auth" is a 3-digit number the caller speaks, matched against `customer_records.json` — no real multi-factor check. `lookup_customer` does compare the caller's actual phone number (from Vapi) against the record's registered `phone` field and returns a `phone_verified` flag, but the fictional records use placeholder numbers (`+91TESTNUM0X`) that can never match a real caller ID, so this check is informational only here, not enforced. **Production fix**: either require phone-match as a hard gate (caller's number must equal the registered number before any account details are shared), or add a second factor (OTP sent to the registered number, DOB, last 4 of card) since a 3-digit guess space (1000 combinations) is not acceptable account-access control on its own.

## Limitations & long-term fix
- Mock backend has no real payment gateway integration — real version would call Razorpay's internal retry API with idempotency keys and PCI-scoped tooling (no card data ever reaches the LLM).
- No multi-language support in this demo — production would need locale-aware voice + prompts.
- No retry/backoff or call-attempt cadence logic (e.g., "try 3x over 5 days, respect DND hours") — would add a scheduler (e.g., Temporal/cron) for production.
- No consent/DND/TRAI compliance check — production must integrate regulatory calling-hour and consent checks before dialing.
- See **Security** section above for the webhook-auth, SMS-destination, and identity-verification gaps and their fixes.
