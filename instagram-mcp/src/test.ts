import test from "node:test";
import assert from "node:assert/strict";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { InstagramClient } from "./instagram.js";
import { createServer } from "./tools.js";

type Call = { method: string; url: URL; body: string };

async function setup(enableWrites: boolean, handler: (c: Call) => unknown) {
  const calls: Call[] = [];
  const fetchImpl = (async (url: URL, init: RequestInit) => {
    const call = { method: init.method ?? "GET", url, body: String(init.body ?? "") };
    calls.push(call);
    const out = handler(call);
    return new Response(JSON.stringify(out), { status: (out as any)?.error ? 400 : 200 });
  }) as unknown as typeof fetch;
  const ig = new InstagramClient({ token: "t", userId: "me", version: "v23.0", fetchImpl });
  const server = createServer(ig, { enableWrites });
  const [a, b] = InMemoryTransport.createLinkedPair();
  const client = new Client({ name: "t", version: "1" });
  await Promise.all([server.connect(a), client.connect(b)]);
  return { client, calls };
}

test("writes are hidden by default", async () => {
  const { client } = await setup(false, () => ({}));
  const names = (await client.listTools()).tools.map((t) => t.name);
  assert.ok(names.includes("instagram_list_media") && names.includes("search") && names.includes("fetch"));
  assert.ok(!names.includes("instagram_publish_media"));
});

test("list_media passes paging and returns cursor", async () => {
  const { client, calls } = await setup(false, () => ({ data: [{ id: "1" }], paging: { cursors: { after: "abc" } } }));
  const r: any = await client.callTool({ name: "instagram_list_media", arguments: { limit: 5 } });
  assert.equal(r.structuredContent.next_cursor, "abc");
  assert.equal(calls[0].url.searchParams.get("limit"), "5");
});

test("API errors become actionable tool errors", async () => {
  const { client } = await setup(false, () => ({ error: { message: "bad", code: 190 } }));
  const r: any = await client.callTool({ name: "instagram_get_profile", arguments: {} });
  assert.equal(r.isError, true);
  assert.match(r.content[0].text, /expired/);
});

test("publish IMAGE: create container, poll, publish", async () => {
  const { client, calls } = await setup(true, (c) => {
    if (c.method === "POST" && c.url.pathname.endsWith("/me/media")) return { id: "C1" };
    if (c.url.pathname.endsWith("/C1")) return { status_code: "FINISHED" };
    if (c.url.pathname.endsWith("/media_publish")) return { id: "M1" };
    return { id: "M1", permalink: "https://instagram.com/p/x" };
  });
  const r: any = await client.callTool({ name: "instagram_publish_media", arguments: { type: "IMAGE", image_url: "https://x.test/a.jpg", caption: "hi" } });
  assert.equal(r.structuredContent.published.permalink, "https://instagram.com/p/x");
  assert.match(calls[0].body, /image_url=/);
  assert.match(calls.find((c) => c.url.pathname.endsWith("media_publish"))!.body, /creation_id=C1/);
});

test("publish validates missing url", async () => {
  const { client } = await setup(true, () => ({}));
  const r: any = await client.callTool({ name: "instagram_publish_media", arguments: { type: "REELS" } });
  assert.equal(r.isError, true);
});

test("search filters captions", async () => {
  const { client } = await setup(false, () => ({ data: [{ id: "1", caption: "Sunset render", permalink: "u1" }, { id: "2", caption: "Cat", permalink: "u2" }] }));
  const r: any = await client.callTool({ name: "search", arguments: { query: "render" } });
  assert.deepEqual(JSON.parse(r.content[0].text).results.map((x: any) => x.id), ["1"]);
});
