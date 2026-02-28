# webhook-repo

A Flask application that receives GitHub webhook events, stores them in MongoDB,
and serves a live-updating activity feed UI that polls for changes every 15 seconds.

---

## Architecture

```
action-repo (GitHub)
    │  Push / Pull-Request / Merge
    ▼
/webhook  ──▶  app.py (Flask)  ──▶  MongoDB (github_events.events)
                                          ▲
                          UI polls /events every 15 s
```

---

## Quick Start (local development)

### Prerequisites
- Python 3.9+
- MongoDB running locally **or** a free [MongoDB Atlas](https://www.mongodb.com/atlas) cluster
- [ngrok](https://ngrok.com/) (to expose localhost to GitHub webhooks)

### 1 – Clone & install dependencies

```bash
git clone https://github.com/<you>/webhook-repo.git
cd webhook-repo
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2 – Configure environment

```bash
cp .env.example .env
# Edit .env and set MONGO_URI (and optionally GITHUB_WEBHOOK_SECRET)
```

### 3 – Run the app

```bash
flask run          # or: python app.py
# Listening on http://127.0.0.1:5000
```

### 4 – Expose with ngrok

```bash
ngrok http 5000
# Note the Forwarding URL, e.g. https://abc123.ngrok.io
```

### 5 – Configure the GitHub webhook on action-repo

1. Go to **action-repo → Settings → Webhooks → Add webhook**
2. **Payload URL**: `https://abc123.ngrok.io/webhook`
3. **Content type**: `application/json`
4. **Secret**: (optional) paste the same value you put in `.env`
5. **Events to trigger**: select *individual events* → ✅ Pushes, ✅ Pull requests
6. Click **Add webhook**

### 6 – Open the UI

Navigate to `http://127.0.0.1:5000` — the feed will populate as you push or
open PRs on **action-repo**.

---

## Deployment (Render / Railway / Heroku)

1. Set the environment variables `MONGO_URI` and optionally `GITHUB_WEBHOOK_SECRET`
   in your hosting dashboard.
2. The `Procfile` (`gunicorn app:app`) is used automatically.
3. Update the webhook Payload URL in **action-repo** to point at your live domain.

---

## API Reference

| Method | Path       | Description                                    |
|--------|------------|------------------------------------------------|
| POST   | `/webhook` | GitHub webhook receiver                        |
| GET    | `/events`  | Returns the 50 most recent events as JSON      |
| GET    | `/`        | Serves the polling UI                          |

### Event JSON schema

```json
{
  "request_id":  "abc123def456",
  "author":      "travis",
  "action":      "PUSH",
  "from_branch": "feature/login",
  "to_branch":   "main",
  "timestamp":   "2021-04-01T21:30:00+00:00",
  "formatted_time": "1st April 2021 - 9:30 PM UTC"
}
```

`action` is one of `"PUSH"`, `"PULL_REQUEST"`, or `"MERGE"`.

---

## UI Display Formats

| Action        | Format |
|---------------|--------|
| PUSH          | `"travis" pushed to "main" on 1st April 2021 - 9:30 PM UTC` |
| PULL_REQUEST  | `"travis" submitted a pull request from "feature" to "main" on …` |
| MERGE         | `"travis" merged branch "dev" to "master" on …` |

The UI never shows the same event twice (deduplication by request_id + action + timestamp)
and refreshes every **15 seconds**.

---

## Project Structure

```
webhook-repo/
├── app.py              # Flask app – webhook receiver, API, UI server
├── templates/
│   └── index.html      # Single-page polling UI
├── requirements.txt
├── Procfile            # For Heroku/Render deployment
├── .env.example        # Environment variable template
└── README.md
```
