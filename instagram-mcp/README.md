# instagram-mcp

MCP server for the Instagram API (Instagram Login). One codebase, two transports:

- **stdio** for Claude Desktop / Claude Code
- **Streamable HTTP** (`/mcp`, stateless JSON) for Claude custom connectors and ChatGPT connectors

Works with Business and Creator accounts only (Meta API restriction).

## Setup

1. In the Meta App Dashboard, create an app, add **Instagram > API setup with Instagram login**, add your account as an Instagram tester, and generate a token with scopes `instagram_business_basic`, `instagram_business_manage_insights`, `instagram_business_content_publish`, `instagram_business_manage_comments`.
2. Exchange for a long-lived token (60 days) and refresh it before expiry.
3. `cp .env.example .env`, fill `INSTAGRAM_ACCESS_TOKEN`.

```
npm install && npm run build && npm test
```

## Claude (stdio)

```json
{
  "mcpServers": {
    "instagram": {
      "command": "node",
      "args": ["/abs/path/instagram-mcp/dist/index.js"],
      "env": { "INSTAGRAM_ACCESS_TOKEN": "...", "INSTAGRAM_ENABLE_WRITES": "0" }
    }
  }
}
```

Claude Code: `claude mcp add instagram -e INSTAGRAM_ACCESS_TOKEN=... -- node /abs/path/instagram-mcp/dist/index.js`

## ChatGPT / remote Claude (HTTP)

```
PORT=3000 MCP_AUTH_TOKEN=<secret> INSTAGRAM_ACCESS_TOKEN=... npm run start:http
```

Deploy it somewhere with HTTPS (Fly, Render, Cloud Run, or `cloudflared tunnel` for testing), then add `https://your-host/mcp` as a connector:

- **ChatGPT**: Settings > Connectors > Advanced > Developer mode > Create. ChatGPT cannot send a static bearer header from the UI, so for ChatGPT either leave `MCP_AUTH_TOKEN` unset behind an unguessable path/IP allowlist, or put an OAuth proxy in front. Do not leave a public, unauthenticated server pointing at your token with writes enabled.
- **Claude**: Settings > Connectors > Add custom connector. Same auth caveat; Claude supports OAuth, not a static header, in the UI. stdio avoids the problem.

The `search` and `fetch` tools exist for ChatGPT deep research and company knowledge compatibility.

## Tools

Read (always on): `instagram_get_profile`, `instagram_list_media`, `instagram_get_media`, `instagram_get_media_insights`, `instagram_get_account_insights`, `instagram_list_comments`, `instagram_business_discovery`, `instagram_get_publishing_limit`, `search`, `fetch`.

Write (only if `INSTAGRAM_ENABLE_WRITES=1`): `instagram_publish_media` (image, reel, story, carousel), `instagram_reply_to_comment`, `instagram_set_comment_hidden`, `instagram_delete_comment`.

Writes are off by default because publishing and replying are public and hard to undo.

## Limits

100 API-published posts per 24h. Insights windows max 30 days. Hashtag search and DMs are not included (they need Facebook Login / Messenger permissions and app review).
