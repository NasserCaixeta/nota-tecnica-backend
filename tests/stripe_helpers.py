"""Sign serialized test webhook bodies, without bypassing the actual HTTP handler."""

import hashlib
import hmac
import json
import time

SECRET = "whsec_" + "test-webhook-secret-".ljust(40, "x")


def signature(body, secret=SECRET, timestamp=None):
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(
        secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


def event(
    event_id="evt_one", resource_id="pi_one", *, kind="payment_intent.succeeded", **object_fields
):
    return {
        "id": event_id,
        "type": kind,
        "livemode": False,
        "created": int(time.time()),
        "data": {
            "object": {
                "id": resource_id,
                "metadata": {"product": "history_access"},
                **object_fields,
            }
        },
    }


def stripe_post(client, payload, *, secret=SECRET, timestamp=None):
    body = json.dumps(payload, separators=(",", ":")).encode()
    return client.post(
        "/api/v1/payments/webhooks/stripe",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": signature(body, secret, timestamp),
        },
    )
