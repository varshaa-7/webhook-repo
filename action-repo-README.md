# action-repo

This is the **source repository** used to trigger GitHub webhook events.

It exists solely to generate Push, Pull Request, and Merge events that
are captured by [webhook-repo](https://github.com/<you>/webhook-repo).

## Setup

1. Go to **Settings → Webhooks → Add webhook** in this repo.
2. Set the **Payload URL** to your `webhook-repo` endpoint:
   ```
   https://<your-domain>/webhook
   ```
3. **Content type**: `application/json`
4. Choose **individual events**: ✅ Pushes, ✅ Pull requests
5. Save.

Any push or pull request on this repo will now appear on the
**webhook-repo** activity feed UI in real time.
