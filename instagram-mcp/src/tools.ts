import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { InstagramClient, InstagramError } from "./instagram.js";

const MEDIA_FIELDS = "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count,thumbnail_url,media_url";
const MAX_CHARS = 25_000;

type Result = { content: { type: "text"; text: string }[]; structuredContent?: Record<string, unknown>; isError?: boolean };

function ok(data: Record<string, unknown>): Result {
  let text = JSON.stringify(data, null, 2);
  if (text.length > MAX_CHARS) text = text.slice(0, MAX_CHARS) + "\n...[truncated; use limit/after to page]";
  return { content: [{ type: "text", text }], structuredContent: data };
}

function fail(e: unknown): Result {
  const msg = e instanceof InstagramError ? e.message : `Unexpected error: ${(e as Error).message}`;
  return { content: [{ type: "text", text: msg }], isError: true };
}

async function guard(fn: () => Promise<Record<string, unknown>>): Promise<Result> {
  try {
    return ok(await fn());
  } catch (e) {
    return fail(e);
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const READ = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true } as const;
const WRITE = { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true } as const;
const DESTROY = { readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: true } as const;

const pagingShape = {
  limit: z.number().int().min(1).max(50).default(10).describe("Items per page (1-50)"),
  after: z.string().optional().describe("Pagination cursor from a previous response's `next_cursor`"),
};

export function createServer(ig: InstagramClient, opts: { enableWrites: boolean }): McpServer {
  const server = new McpServer({ name: "instagram-mcp", version: "1.0.0" });
  const me = ig.userId;

  server.registerTool(
    "instagram_get_profile",
    {
      title: "Get Instagram profile",
      description: "Get the connected account's profile: username, name, bio, follower/following/media counts, website.",
      inputSchema: {},
      annotations: READ,
    },
    () =>
      guard(() =>
        ig.get(me, { fields: "user_id,username,name,account_type,biography,website,followers_count,follows_count,media_count,profile_picture_url" }),
      ),
  );

  server.registerTool(
    "instagram_list_media",
    {
      title: "List Instagram media",
      description: "List the account's posts, reels and carousels, newest first, with engagement counts.",
      inputSchema: pagingShape,
      annotations: READ,
    },
    ({ limit, after }) =>
      guard(async () => {
        const r = await ig.get(`${me}/media`, { fields: MEDIA_FIELDS, limit, after });
        return { media: r.data, next_cursor: r.paging?.cursors?.after ?? null };
      }),
  );

  server.registerTool(
    "instagram_get_media",
    {
      title: "Get Instagram media item",
      description: "Get one post by ID, including carousel children.",
      inputSchema: { media_id: z.string().describe("Instagram media ID") },
      annotations: READ,
    },
    ({ media_id }) =>
      guard(() => ig.get(media_id, { fields: `${MEDIA_FIELDS},children{id,media_type,media_url,thumbnail_url}` })),
  );

  server.registerTool(
    "instagram_get_media_insights",
    {
      title: "Get media insights",
      description:
        "Get performance metrics for one post. Common metrics: reach, likes, comments, shares, saved, total_interactions, views (reels: also ig_reels_avg_watch_time, ig_reels_video_view_total_time). Unsupported metrics for the media type return an error.",
      inputSchema: {
        media_id: z.string(),
        metrics: z.array(z.string()).min(1).default(["reach", "likes", "comments", "shares", "saved", "total_interactions"]),
      },
      annotations: READ,
    },
    ({ media_id, metrics }) =>
      guard(async () => {
        const r = await ig.get(`${media_id}/insights`, { metric: metrics.join(",") });
        return { insights: r.data };
      }),
  );

  server.registerTool(
    "instagram_get_account_insights",
    {
      title: "Get account insights",
      description:
        "Account-level metrics over a time window. Common metrics: reach, views, accounts_engaged, total_interactions, likes, comments, shares, saves, replies, follows_and_unfollows, profile_links_taps. Use metric_type=total_value for totals (supports breakdown such as media_product_type) or time_series for per-day values. Max window 30 days. since/until are ISO dates or Unix seconds.",
      inputSchema: {
        metrics: z.array(z.string()).min(1).default(["reach", "views", "accounts_engaged"]),
        period: z.enum(["day", "lifetime"]).default("day"),
        metric_type: z.enum(["total_value", "time_series"]).default("total_value"),
        breakdown: z.string().optional().describe("e.g. media_product_type, follow_type, contact_button_type"),
        since: z.string().optional(),
        until: z.string().optional(),
      },
      annotations: READ,
    },
    ({ metrics, period, metric_type, breakdown, since, until }) =>
      guard(async () => {
        const r = await ig.get(`${me}/insights`, {
          metric: metrics.join(","),
          period,
          metric_type,
          breakdown,
          since: toUnix(since),
          until: toUnix(until),
        });
        return { insights: r.data };
      }),
  );

  server.registerTool(
    "instagram_list_comments",
    {
      title: "List comments",
      description: "List top-level comments on a post, with replies.",
      inputSchema: { media_id: z.string(), ...pagingShape },
      annotations: READ,
    },
    ({ media_id, limit, after }) =>
      guard(async () => {
        const r = await ig.get(`${media_id}/comments`, {
          fields: "id,text,username,timestamp,like_count,hidden,replies{id,text,username,timestamp}",
          limit,
          after,
        });
        return { comments: r.data, next_cursor: r.paging?.cursors?.after ?? null };
      }),
  );

  server.registerTool(
    "instagram_business_discovery",
    {
      title: "Look up another business account",
      description:
        "Public stats and recent media for another Instagram Business/Creator account by username. Personal accounts are not available.",
      inputSchema: { username: z.string().describe("Username without @"), media_limit: z.number().int().min(0).max(25).default(5) },
      annotations: READ,
    },
    ({ username, media_limit }) =>
      guard(async () => {
        const handle = username.replace(/^@/, "");
        if (!/^[A-Za-z0-9._]{1,30}$/.test(handle)) throw new InstagramError("Invalid username.");
        const r = await ig.get(me, {
          fields: `business_discovery.username(${handle}){username,name,biography,website,followers_count,follows_count,media_count,profile_picture_url,media.limit(${media_limit}){id,caption,media_type,permalink,timestamp,like_count,comments_count}}`,
        });
        return r.business_discovery ?? {};
      }),
  );

  server.registerTool(
    "instagram_get_publishing_limit",
    {
      title: "Get publishing quota",
      description: "Check how many API-published posts have been used in the rolling 24h window (limit is 100).",
      inputSchema: {},
      annotations: READ,
    },
    () => guard(async () => ({ quota: (await ig.get(`${me}/content_publishing_limit`, { fields: "quota_usage,config" })).data })),
  );

  // ChatGPT deep research / company-knowledge connectors expect `search` and `fetch`.
  server.registerTool(
    "search",
    {
      title: "Search my Instagram posts",
      description: "Search the account's recent posts (last ~100) by caption text. Returns matching post IDs for use with `fetch`.",
      inputSchema: { query: z.string().describe("Text to look for in captions; case-insensitive") },
      annotations: READ,
    },
    async ({ query }) => {
      try {
        const q = query.toLowerCase();
        const r = await ig.get(`${me}/media`, { fields: "id,caption,permalink,timestamp,media_type", limit: 50 });
        let items: any[] = r.data ?? [];
        if (r.paging?.cursors?.after && r.paging?.next) {
          const r2 = await ig.get(`${me}/media`, { fields: "id,caption,permalink,timestamp,media_type", limit: 50, after: r.paging.cursors.after });
          items = items.concat(r2.data ?? []);
        }
        const results = items
          .filter((m) => (m.caption ?? "").toLowerCase().includes(q))
          .map((m) => ({ id: m.id, title: (m.caption ?? "(no caption)").split("\n")[0].slice(0, 80), url: m.permalink }));
        return { content: [{ type: "text" as const, text: JSON.stringify({ results }) }] };
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "fetch",
    {
      title: "Fetch an Instagram post",
      description: "Fetch a post by ID (from `search`) with caption, engagement and metadata.",
      inputSchema: { id: z.string() },
      annotations: READ,
    },
    async ({ id }) => {
      try {
        const m = await ig.get(id, { fields: MEDIA_FIELDS });
        const doc = {
          id: m.id,
          title: (m.caption ?? "(no caption)").split("\n")[0].slice(0, 80),
          text: m.caption ?? "",
          url: m.permalink,
          metadata: { type: m.media_type, posted: m.timestamp, likes: m.like_count, comments: m.comments_count },
        };
        return { content: [{ type: "text" as const, text: JSON.stringify(doc) }] };
      } catch (e) {
        return fail(e);
      }
    },
  );

  if (!opts.enableWrites) return server;

  server.registerTool(
    "instagram_publish_media",
    {
      title: "Publish to Instagram",
      description:
        "PUBLISHES PUBLICLY. Create and publish a post. type=IMAGE needs image_url; REELS needs video_url; STORIES needs image_url or video_url; CAROUSEL needs 2-10 items. All URLs must be publicly reachable (JPEG for images, MP4/MOV for video). Always confirm caption and media with the user before calling. Waits for video processing (up to ~5 min).",
      inputSchema: {
        type: z.enum(["IMAGE", "REELS", "STORIES", "CAROUSEL"]),
        caption: z.string().max(2200).optional(),
        image_url: z.string().url().optional(),
        video_url: z.string().url().optional(),
        cover_url: z.string().url().optional().describe("Reels cover image"),
        share_to_feed: z.boolean().optional().describe("Reels only; default true"),
        alt_text: z.string().max(1000).optional(),
        location_id: z.string().optional(),
        items: z
          .array(z.object({ image_url: z.string().url().optional(), video_url: z.string().url().optional() }))
          .min(2)
          .max(10)
          .optional()
          .describe("Carousel children"),
      },
      annotations: WRITE,
    },
    (a) =>
      guard(async () => {
        let creation: string;
        if (a.type === "CAROUSEL") {
          if (!a.items) throw new InstagramError("CAROUSEL requires `items`.");
          const ids: string[] = [];
          for (const it of a.items) {
            if (!!it.image_url === !!it.video_url) throw new InstagramError("Each carousel item needs exactly one of image_url or video_url.");
            const c = await ig.post(`${me}/media`, {
              is_carousel_item: true,
              image_url: it.image_url,
              video_url: it.video_url,
              media_type: it.video_url ? "VIDEO" : undefined,
            });
            await waitReady(ig, c.id);
            ids.push(c.id);
          }
          creation = (await ig.post(`${me}/media`, { media_type: "CAROUSEL", children: ids.join(","), caption: a.caption, location_id: a.location_id })).id;
        } else {
          if (a.type === "IMAGE" && !a.image_url) throw new InstagramError("IMAGE requires image_url.");
          if (a.type === "REELS" && !a.video_url) throw new InstagramError("REELS requires video_url.");
          if (a.type === "STORIES" && !!a.image_url === !!a.video_url) throw new InstagramError("STORIES requires exactly one of image_url or video_url.");
          creation = (
            await ig.post(`${me}/media`, {
              media_type: a.type === "IMAGE" ? undefined : a.type,
              image_url: a.image_url,
              video_url: a.video_url,
              cover_url: a.cover_url,
              share_to_feed: a.share_to_feed,
              caption: a.caption,
              alt_text: a.alt_text,
              location_id: a.location_id,
            })
          ).id;
        }
        await waitReady(ig, creation);
        const pub = await ig.post(`${me}/media_publish`, { creation_id: creation });
        const m = await ig.get(pub.id, { fields: "id,permalink,media_type,timestamp" });
        return { published: m };
      }),
  );

  server.registerTool(
    "instagram_reply_to_comment",
    {
      title: "Reply to comment",
      description: "PUBLIC. Post a reply to a comment. Confirm the text with the user first.",
      inputSchema: { comment_id: z.string(), message: z.string().min(1).max(2200) },
      annotations: WRITE,
    },
    ({ comment_id, message }) => guard(() => ig.post(`${comment_id}/replies`, { message })),
  );

  server.registerTool(
    "instagram_set_comment_hidden",
    {
      title: "Hide or unhide comment",
      description: "Hide a comment from public view, or unhide it. Reversible.",
      inputSchema: { comment_id: z.string(), hidden: z.boolean() },
      annotations: { ...WRITE, idempotentHint: true },
    },
    ({ comment_id, hidden }) => guard(() => ig.post(comment_id, { hide: hidden })),
  );

  server.registerTool(
    "instagram_delete_comment",
    {
      title: "Delete comment",
      description: "PERMANENTLY delete a comment. Cannot be undone. Prefer instagram_set_comment_hidden unless the user asked to delete.",
      inputSchema: { comment_id: z.string() },
      annotations: DESTROY,
    },
    ({ comment_id }) => guard(() => ig.del(comment_id)),
  );

  return server;
}

async function waitReady(ig: InstagramClient, containerId: string, timeoutMs = 300_000) {
  const start = Date.now();
  for (;;) {
    const s = await ig.get(containerId, { fields: "status_code,status" });
    if (s.status_code === "FINISHED") return;
    if (s.status_code === "ERROR" || s.status_code === "EXPIRED") {
      throw new InstagramError(`Media processing failed: ${s.status_code}${s.status ? ` (${s.status})` : ""}. Check URL is public and format is supported.`);
    }
    if (Date.now() - start > timeoutMs) throw new InstagramError(`Timed out waiting for media processing (container ${containerId}).`);
    await sleep(3000);
  }
}

function toUnix(v?: string): string | undefined {
  if (!v) return undefined;
  if (/^\d+$/.test(v)) return v;
  const t = Date.parse(v);
  if (Number.isNaN(t)) throw new InstagramError(`Invalid date: ${v}`);
  return String(Math.floor(t / 1000));
}
