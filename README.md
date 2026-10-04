# 📞 Autopay Recovery Voice Agent

**A production-style voice agent that calls customers about failed payments — and actually gets them paid.**

Built on [Vapi](https://vapi.ai) · Python / FastAPI backend · Real Twilio SMS delivery

---

A voice agent that calls customers with failed autopay payments, verifies
their identity, explains why the payment failed, and offers to either retry
the charge or send a secure link to update their payment method — the same
recovery flow a human collections agent would run, automated end to end.

This was built as a working demonstration against 10 fictional customer
records, with a **real phone call**, **real identity verification logic**,
and a **real SMS sent on delivery**. Full architecture, design decisions,
and known limitations are documented in [PLAN.md](PLAN.md); this README
covers setup, how to run it, and what the two included test cases prove.

| | |
|---|---|
| 📱 **Live demo number** | `+1 (415) 300-9362` |
| 🧪 **Test records** | 10 fictional customers, `cust_001` – `cust_010` |
| ✅ **Proven end to end** | 2 recorded calls — one success, one failure-with-fallback |
| 🔒 **Real data** | None. Everything is fictional or mocked. |

---

## How it works

```
caller dials in
      │
      ▼
① AI discloses itself + recording notice
      │
      ▼
② asks for a 3-digit customer number
      │
      ▼
③ lookup_customer — verifies the account BEFORE saying anything about it
      │
      ├── not found → apologizes, logs wrong_contact, ends call
      │
      ▼ found
④ states the real failure reason + amount (from the backend, never invented)
      │
      ▼
⑤ offers: retry now, or send a secure SMS link
      │
      ├── retry_payment ──→ success → confirms, done
      │         └────────→ fail → offers the SMS link instead
      │
      └── offer_payment_link ──→ real SMS sent via Twilio
      │
      ▼
⑥ log_outcome — structured result recorded, every single call
```

The conversation logic, the identity check, and the retry/fallback branching
are all real. What's mocked is the payment gateway itself and the exact
content of the SMS (see [Limitations](#️-limitations) below) — there is no
real money or real customer data anywhere in this project.

---

## 📂 Repository layout

```
voice-agent/
├── README.md                 you are here
├── PLAN.md                   architecture, design rationale, security notes, limitations
├── requirements.txt
├── .env.example               every config value this project needs, documented
├── src/
│   ├── customer_records.json  10 fictional customers used for the demo
│   ├── assistant_config.json  the Vapi assistant definition (prompt, tools, voice)
│   ├── mock_backend.py        FastAPI service simulating the payment system
│   ├── webhook_handler.py     FastAPI service Vapi calls mid-conversation to run tools
│   └── trigger_calls.py       outbound-calling script, kept for the production path (see PLAN.md)
├── tests/
│   └── test_mock_backend.py   unit tests for every backend endpoint and edge case
└── results/
    ├── success_case.md        full transcript + logged outcome: retry succeeds
    └── failure_case.md        full transcript + logged outcome: retry fails, SMS link sent
```

---

## 🚀 Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

| Variable | Where to get it |
|---|---|
| `VAPI_API_KEY` | vapi.ai dashboard → API Keys |
| `VAPI_ASSISTANT_ID` | created after importing `src/assistant_config.json` into Vapi (dashboard, or `POST /assistant`) |
| `VAPI_PHONE_NUMBER_ID` | the Vapi phone number assigned to this assistant |
| `WEBHOOK_BASE_URL` | your public tunnel URL (see below) |
| `TWILIO_*` | optional — only needed if you want `offer_payment_link` to send a real SMS |

Expose the webhook publicly so Vapi can reach it during a live call:

```bash
ngrok http 8000
# paste the https URL into WEBHOOK_BASE_URL in .env, and into the
# assistant's Server URL field in the Vapi dashboard
```

---

## ▶️ Running it locally

Three processes, three terminals:

```bash
# Terminal 1 — mock payment backend
uvicorn src.mock_backend:app --port 8001

# Terminal 2 — webhook handler (Vapi calls this mid-conversation)
uvicorn src.webhook_handler:app --port 8000

# Terminal 3
ngrok http 8000
```

## ☁️ Deploying it (Render)

ngrok tunnels die the moment your laptop sleeps or the process stops —
fine for development, not something a reviewer can rely on later. For a
URL that stays up on its own, `src/app.py` combines the backend and the
webhook handler into a single FastAPI app (same logic as the two local
services, just merged so Render only needs to run one process), and
`render.yaml` deploys it as a Render Blueprint:

1. Push this repo to GitHub.
2. [render.com](https://render.com) → **New → Blueprint** → connect the repo.
   Render reads `render.yaml` and sets up the service automatically.
3. Fill in the environment variables it asks for (`TWILIO_*`,
   `VAPI_WEBHOOK_SECRET` — all optional, the service runs fine without them).
4. Once deployed, copy the Render URL (`https://autopay-voice-agent.onrender.com`)
   and paste it into the Vapi assistant/phone number's **Server URL** field as
   `<render-url>/vapi/tool-call`, replacing the ngrok URL.

Render's free tier spins the service down after 15 minutes of inactivity and
takes a few seconds to wake back up on the next request — fine for a demo
that gets called occasionally, not a production SLA. See
[PLAN.md](PLAN.md) for what a real always-on deployment would need instead.

Then call the Vapi phone number shown in the dashboard — for this
submission, that's **+1 (415) 300-9362**. When asked, give any 3-digit
number from `src/customer_records.json` (001 through 010) to role-play
that customer. Every call's final outcome is appended to `src/results.json`.

> **Why inbound, not outbound?** Vapi's free-trial phone numbers can receive
> calls but can't place them — true outbound dialing needs an imported,
> paid-or-verified number (Twilio, Vonage). For this assignment I kept the
> demo inbound: you call the agent instead of the agent calling you, and it
> asks for your customer number to identify you rather than assuming who it
> dialed. The conversation logic is identical either way.
> `src/trigger_calls.py` implements the outbound path and is ready to use
> once a verified outbound number is available — see PLAN.md's
> "Call direction note" for the full reasoning.

---

## 🧪 Test cases

Two real calls are included as evidence this works end to end, not just in
isolated unit tests:

| Case | Customer | Result | Details |
|---|---|---|---|
| ✅ **Success** | cust_003 (Meera Iyer) | `payment_recovered` | [results/success_case.md](results/success_case.md) — full transcript, retry succeeds first try |
| ⚠️ **Failure → fallback** | cust_001 (Asha Rao) | `link_sent` | [results/failure_case.md](results/failure_case.md) — retry fails as designed, agent sends a real SMS link, delivery confirmed |

Both are backed by the raw logged outcomes in `src/results.json`.

---

## 🔬 Automated tests

```bash
python tests/test_mock_backend.py
```

Covers every backend endpoint: customer lookup (found, not found, phone
verification), retry logic per fictional record, unknown-customer handling,
and ID normalization across the casing/formatting variations a voice
transcript can produce (`cust_001`, `CUST-001`, `Cust 001`). No framework or
fixtures — a single `assert`-based script that fails loudly if any of this
logic regresses.

---

## 🔐 Safety

- All 10 customer records are fictional; no real customer data is used
  anywhere in this project.
- No card number, CVV, or OTP is ever requested or accepted — this is a hard
  rule in the system prompt, reinforced by the fact that no tool in this
  codebase accepts that kind of input in the first place.
- `trigger_calls.py` (the outbound path) refuses to dial any number that
  isn't explicitly allowlisted in `.env`, so it can never accidentally call
  a real phone number.
- The SMS destination number is always taken from Vapi's verified caller ID,
  never from anything the model or caller supplies — this closes off using
  the SMS endpoint to message arbitrary numbers.

---

## ⚠️ Limitations

Documented in full, with the production fix for each, in
[PLAN.md's Security and Limitations sections](PLAN.md#security). In short:

- The payment gateway is mocked — no real money moves.
- Identity verification is a 3-digit number, intentionally weak for a
  10-record demo; production needs a real second factor.
- The webhook's shared-secret authentication is implemented but left
  unconfigured in this submission (documented explicitly in code, not a
  silent gap) to avoid burning more live-call budget re-verifying it.
- SMS delivery works, but Twilio's trial account only allows a fixed,
  pre-approved template body — the real payment-link copy isn't the actual
  delivered text on a trial account.
