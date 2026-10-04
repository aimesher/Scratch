#!/usr/bin/env node
import express from "express";
import { timingSafeEqual } from "node:crypto";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { InstagramClient, configFromEnv } from "./instagram.js";
import { createServer } from "./tools.js";

const ig = new InstagramClient(configFromEnv());
const enableWrites = process.env.INSTAGRAM_ENABLE_WRITES === "1";

function safeEq(a: string, b: string) {
  const x = Buffer.from(a), y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

async function main() {
  if (!process.argv.includes("--http")) {
    await createServer(ig, { enableWrites }).connect(new StdioServerTransport());
    console.error(`instagram-mcp running on stdio (writes ${enableWrites ? "enabled" : "disabled"})`);
    return;
  }

  const app = express();
  app.use(express.json({ limit: "1mb" }));
  const authToken = process.env.MCP_AUTH_TOKEN;

  app.get("/health", (_req, res) => void res.json({ ok: true }));

  // Stateless: fresh server + transport per request.
  app.post("/mcp", async (req, res) => {
    if (authToken && !safeEq(req.get("authorization") ?? "", `Bearer ${authToken}`)) {
      res.status(401).json({ jsonrpc: "2.0", error: { code: -32001, message: "Unauthorized" }, id: null });
      return;
    }
    const server = createServer(ig, { enableWrites });
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    res.on("close", () => {
      void transport.close();
      void server.close();
    });
    try {
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
    } catch (e) {
      console.error(e);
      if (!res.headersSent) res.status(500).json({ jsonrpc: "2.0", error: { code: -32603, message: "Internal error" }, id: null });
    }
  });
  const noGet = (_req: express.Request, res: express.Response) =>
    void res.status(405).json({ jsonrpc: "2.0", error: { code: -32000, message: "Method not allowed (stateless server)" }, id: null });
  app.get("/mcp", noGet);
  app.delete("/mcp", noGet);

  const port = Number(process.env.PORT || 3000);
  app.listen(port, () => console.error(`instagram-mcp on http://0.0.0.0:${port}/mcp (writes ${enableWrites ? "enabled" : "disabled"}, auth ${authToken ? "on" : "OFF"})`));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
