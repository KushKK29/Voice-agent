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
| ☁️ **Live webhook (deployed)** | [voice-agent-drab-seven.vercel.app](https://voice-agent-drab-seven.vercel.app) |
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
├── README.md                     you are here
├── PLAN.md                       architecture, design rationale, security notes, limitations
├── requirements.txt
├── render.yaml                   Render Blueprint (alternate deploy target, see below)
├── .env.example                   every config value this project needs, documented
├── src/
│   ├── customer_records.json      10 fictional customers used for the demo
│   ├── assistant_config.json      the Vapi assistant definition (prompt, tools, voice)
│   ├── app.py                     combined backend + webhook, used for the live deployment
│   ├── mock_backend.py            backend service, for running locally as two processes
│   ├── webhook_handler.py         webhook service, for running locally as two processes
│   └── trigger_calls.py           outbound-calling script, kept for the production path (see PLAN.md)
├── tests/
│   └── test_mock_backend.py       unit tests for every backend endpoint and edge case
├── results/
│   ├── success_case.md            full transcript + logged outcome: retry succeeds
│   └── failure_case.md            full transcript + logged outcome: retry fails, SMS link sent
└── result-audio-recordings/
    ├── success.wav                actual call audio for the success case
    └── failure.wav                actual call audio for the failure/fallback case
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

## ☁️ Live deployment

ngrok tunnels die the moment a laptop sleeps or the process stops — fine for
development, not something a reviewer can rely on later. `src/app.py`
combines the backend and the webhook handler into a single FastAPI app (same
logic as the two local services, just merged into one process) and is
deployed live at:

**[`voice-agent-drab-seven.vercel.app`](https://voice-agent-drab-seven.vercel.app)**

This is the URL wired into the Vapi assistant's **Server URL** field right
now, so calling **+1 (415) 300-9362** hits this live deployment, not a local
machine. No cold-start delay on Vapi's side — Vercel's serverless functions
respond fast enough that the call flow doesn't feel any different from
running locally.

To deploy your own copy to Vercel: connect this repo at
[vercel.com](https://vercel.com), set the framework preset to **FastAPI**,
and set `src/app.py`'s `app` object as the entrypoint. Add the same
environment variables as `.env.example` under the project's Environment
Variables settings.

`render.yaml` is also included as an alternate deploy target (Render
Blueprint) if you'd rather run this on Render instead — same `src/app.py`,
just a different host. Render's free tier spins the service down after
inactivity and takes a few seconds to wake back up on the next request,
which is why Vercel is what's actually live for this submission.

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

## 📞 Try it yourself

1. **Call +1 (415) 300-9362.** It's live right now, hitting the Vercel
   deployment above, not a machine that needs to be running on my end.
2. The agent will disclose that it's an AI and that the call may be
   recorded, then ask for a **3-digit customer number**.
3. **Give it any number from 001 to 010** (e.g. "zero zero three" or just
   "three") — these map to the 10 fictional customers in
   `src/customer_records.json`. Full list of which ones succeed or fail on
   retry, and why, is in [PLAN.md](PLAN.md).
4. The agent looks the number up, confirms it found an account, and states
   the (fictional) reason the last autopay payment failed.
5. **Say "retry"** to have it attempt the payment again, or **say "send me
   a link"** to have it text a payment-update link to the number you're
   calling from (a real SMS, sent via Twilio).
6. Say "no" / "that's all" / hang up to end the call. The outcome gets
   logged to `src/results.json` either way.

**What happens with a number outside 001–010?** Try it — say "999" or any
other 3-digit number not in the records file. The agent calls
`lookup_customer`, gets `found: false` back, and tells you it couldn't find
an account with that number rather than inventing one. It'll ask you to try
again once; if that also doesn't match a real record, it apologizes, logs
the outcome as `wrong_contact`, and ends the call. This is deliberate — the
agent never fabricates account details for an ID it can't verify, which is
the same `lookup_customer` check that runs for every valid ID too, just
returning `found: false` instead of the account details.

---

## 🧪 Test cases

Two real calls are included as evidence this works end to end, not just in
isolated unit tests:

| Case | Customer | Result | Transcript | Audio |
|---|---|---|---|---|
| ✅ **Success** | cust_003 (Meera Iyer) | `payment_recovered` | [results/success_case.md](results/success_case.md) | [recording](result-audio-recordings/success.wav) · [Drive link](https://drive.google.com/file/d/1ZMzRBA9ltGK9_fPQsoH5BiKUMqafJn9_/view?usp=sharing) |
| ⚠️ **Failure → fallback** | cust_001 (Asha Rao) | `link_sent` | [results/failure_case.md](results/failure_case.md) | [recording](result-audio-recordings/failure.wav) · [Drive link](https://drive.google.com/file/d/1JlKlCUidK79c9FZKCFt5pnTABLJcP0Rt/view?usp=sharing) |

Transcripts include the full back-and-forth plus every tool call's result.
The `.wav` files are the actual call recordings pulled from Vapi's dashboard;
the Drive links are there so you can stream them straight from the browser
without downloading — same audio, whichever's more convenient.

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
