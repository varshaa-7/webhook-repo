"""
webhook-repo/app.py
--------------------
Flask application that:
  1. Receives GitHub webhook events (push, pull_request, merge).
  2. Stores normalised event data in MongoDB.
  3. Serves a lightweight polling UI at the root URL.
  4. Exposes a /events API endpoint consumed by the UI every 15 seconds.
"""

import os
import hashlib
import hmac
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template, abort
from pymongo import MongoClient, DESCENDING

# ---------------------------------------------------------------------------
# App & DB configuration
# ---------------------------------------------------------------------------

app = Flask(__name__)

# Set MONGO_URI in your environment (defaults to localhost for local dev)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
GITHUB_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")  # optional HMAC validation

client = MongoClient(MONGO_URI)
db = client["github_events"]
events_collection = db["events"]

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def verify_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Validate the X-Hub-Signature-256 header when a secret is configured."""
    if not GITHUB_SECRET:
        return True  # skip validation if no secret configured
    if not signature_header:
        return False
    hash_algo, _, signature = signature_header.partition("=")
    expected = hmac.new(
        GITHUB_SECRET.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def utc_now_str() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def format_timestamp(iso_str: str) -> str:
    """
    Convert an ISO-8601 datetime string to a human-readable UTC label.
    Example: '1st April 2021 - 9:30 PM UTC'
    """
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return iso_str

    # Ordinal suffix for day
    day = dt.day
    suffix = (
        "th" if 11 <= day <= 13
        else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    )
    return dt.strftime(f"%-d{suffix} %B %Y - %-I:%M %p UTC")


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Receive a GitHub webhook POST, parse the relevant fields and persist
    the event document to MongoDB.

    Supported GitHub events (X-GitHub-Event header):
      - push
      - pull_request  (opened / synchronize / closed-without-merge)
      - pull_request  with merged==True  → stored as MERGE
    """
    # --- HMAC signature validation ----------------------------------------
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, sig_header):
        abort(403, "Invalid webhook signature")

    event_type = request.headers.get("X-GitHub-Event", "")
    payload = request.get_json(force=True, silent=True) or {}

    # --- Parse event fields --------------------------------------------------
    document = None

    if event_type == "push":
        # GitHub sends the full ref, e.g. "refs/heads/main" — strip prefix
        to_branch = payload.get("ref", "").replace("refs/heads/", "")
        pusher = payload.get("pusher", {})
        author = pusher.get("name", "unknown")
        request_id = payload.get("after", "")  # latest commit hash after push

        document = {
            "request_id": request_id,
            "author": author,
            "action": "PUSH",
            "from_branch": to_branch,   # for PUSH from == to (same branch)
            "to_branch": to_branch,
            "timestamp": utc_now_str(),
        }

    elif event_type == "pull_request":
        pr = payload.get("pull_request", {})
        action_label = payload.get("action", "")
        is_merged = pr.get("merged", False)

        # Determine stored action type
        if action_label == "closed" and is_merged:
            action = "MERGE"
        elif action_label in ("opened", "reopened", "synchronize"):
            action = "PULL_REQUEST"
        else:
            # Ignore other sub-actions (labeled, assigned, review_requested …)
            return jsonify({"status": "ignored", "reason": f"action={action_label}"}), 200

        author = pr.get("user", {}).get("login", "unknown")
        from_branch = pr.get("head", {}).get("ref", "")
        to_branch = pr.get("base", {}).get("ref", "")
        request_id = str(pr.get("number", ""))  # PR number as ID

        document = {
            "request_id": request_id,
            "author": author,
            "action": action,
            "from_branch": from_branch,
            "to_branch": to_branch,
            "timestamp": utc_now_str(),
        }

    else:
        # Unsupported event type — acknowledge but do nothing
        return jsonify({"status": "ignored", "event": event_type}), 200

    # --- Persist to MongoDB --------------------------------------------------
    if document:
        events_collection.insert_one(document)
        # Remove the non-serialisable ObjectId before logging
        document.pop("_id", None)
        app.logger.info("Stored event: %s", document)

    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# API – latest events for the polling UI
# ---------------------------------------------------------------------------

@app.route("/events", methods=["GET"])
def get_events():
    """
    Return the 50 most recent events as JSON, ordered newest-first.
    The UI polls this endpoint every 15 seconds.
    """
    cursor = events_collection.find(
        {},
        {"_id": 0}  # exclude internal Mongo _id from the response
    ).sort("timestamp", DESCENDING).limit(50)

    events = list(cursor)

    # Attach a formatted timestamp string for each event
    for ev in events:
        ev["formatted_time"] = format_timestamp(ev.get("timestamp", ""))

    return jsonify(events)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the single-page polling dashboard."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
