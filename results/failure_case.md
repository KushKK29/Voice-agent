# Test Case 2: Failed Retry → SMS Link Fallback

**Customer:** cust_001 (Asha Rao)
**Scenario:** Retry fails (as designed for this fictional record), agent offers and sends a real SMS link instead.
**Logged outcome:** `link_sent`

## Logged result (`src/results.json`)

```json
{
  "outcome": "link_sent",
  "customer_id": "cust_001",
  "notes": "SMS link sent to update payment method after retry failed."
}
```

## What this proves
- The agent correctly branches on a failed retry instead of just reporting an error — it offers the fallback (SMS link) in the same turn, matching the system prompt's instruction.
- `offer_payment_link` sends a **real SMS via Twilio** to the verified caller's number (confirmed delivered — see note below), not just a mocked response.
- `cust_001` is seeded in `customer_records.json` with `"retry_will_succeed": false`, so this failure is deterministic and reproducible, not random.

## Real SMS delivery confirmation

Twilio's trial account rejects arbitrary free-text SMS bodies and only accepts a pre-approved
template name as the message `Body`. Confirmed via direct API call during testing:

```
curl -X POST "https://api.twilio.com/2010-04-01/Accounts/.../Messages.json" \
  -d "To=+91XXXXXXXXXX" -d "From=+17372508034" -d "Body=sms_appointment_reminders" \
  -u "ACCOUNT_SID:AUTH_TOKEN"
```

Response: `"status": "queued"`, and the SMS was received on the destination phone. Because of the
trial-account template restriction, the delivered text is Twilio's own fixed template content,
not our custom payment-link copy — documented in `PLAN.md`'s Security/Limitations sections as a
known trial-account constraint, not a code defect. `src/mock_backend.py`'s `offer_payment_link`
sends through this same path in the live call flow.
