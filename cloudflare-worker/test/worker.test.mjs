import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto as crypto } from "node:crypto";
import worker from "../src/index.js";

const GUILD = "111", USER = "222", APP = "333";
const ROLES = [
  { id: "10", name: "Verified" }, { id: "11", name: "Unverified" }, { id: "12", name: "Bots" },
];

// Fake Discord API
let calls;
function mockDiscord({ members = [], putStatus = 204 } = {}) {
  calls = [];
  globalThis.fetch = async (url, init = {}) => {
    const method = init.method || "GET";
    calls.push({ method, url: String(url), body: init.body });
    const u = String(url);
    if (u.endsWith(`/guilds/${GUILD}/roles`)) return Response.json(ROLES);
    if (u.includes(`/guilds/${GUILD}/members?`)) return Response.json(members);
    if (method === "PUT") return new Response(null, { status: putStatus });
    return new Response(null, { status: 204 });
  };
}

async function setup() {
  const kp = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
  const pub = Buffer.from(await crypto.subtle.exportKey("raw", kp.publicKey)).toString("hex");
  const env = { DISCORD_PUBLIC_KEY: pub, DISCORD_GUILD_ID: GUILD, DISCORD_BOT_TOKEN: "test-token" };
  const signed = async (payload, { tamper = false } = {}) => {
    const body = JSON.stringify(payload);
    const ts = String(Date.now());
    const sig = Buffer.from(await crypto.subtle.sign("Ed25519", kp.privateKey, new TextEncoder().encode(ts + body))).toString("hex");
    return new Request("https://w.example/", {
      method: "POST", body: tamper ? body + " " : body,
      headers: { "X-Signature-Ed25519": sig, "X-Signature-Timestamp": ts },
    });
  };
  return { env, signed };
}

const ctxFactory = () => {
  const pending = [];
  return { ctx: { waitUntil: (p) => pending.push(p) }, done: () => Promise.all(pending) };
};

const click = (roles) => ({
  type: 3, application_id: APP, token: "tok", guild_id: GUILD,
  data: { custom_id: "wwa:verify" }, member: { user: { id: USER }, roles },
});

test("PING is answered", async () => {
  const { env, signed } = await setup();
  const res = await worker.fetch(await signed({ type: 1 }), env, ctxFactory().ctx);
  assert.deepEqual(await res.json(), { type: 1 });
});

test("bad signature is rejected with 401", async () => {
  const { env, signed } = await setup();
  const res = await worker.fetch(await signed({ type: 1 }, { tamper: true }), env, ctxFactory().ctx);
  assert.equal(res.status, 401);
});

test("verify click: acks ephemerally, adds Verified, removes Unverified", async () => {
  mockDiscord();
  const { env, signed } = await setup();
  const { ctx, done } = ctxFactory();
  const res = await worker.fetch(await signed(click(["11"])), env, ctx);
  assert.deepEqual(await res.json(), { type: 5, data: { flags: 64 } });
  await done();
  assert.ok(calls.some((c) => c.method === "PUT" && c.url.endsWith(`/members/${USER}/roles/10`)));
  assert.ok(calls.some((c) => c.method === "DELETE" && c.url.endsWith(`/members/${USER}/roles/11`)));
  const last = calls.at(-1);
  assert.match(last.body, /You're verified/);
});

test("already verified users are told so and nothing changes", async () => {
  mockDiscord();
  const { env, signed } = await setup();
  const { ctx, done } = ctxFactory();
  await worker.fetch(await signed(click(["10"])), env, ctx);
  await done();
  assert.ok(!calls.some((c) => c.method === "PUT" || c.method === "DELETE"));
  assert.match(calls.at(-1).body, /already verified/);
});

test("403 from Discord gives the hierarchy hint", async () => {
  mockDiscord({ putStatus: 403 });
  const { env, signed } = await setup();
  const { ctx, done } = ctxFactory();
  await worker.fetch(await signed(click(["11"])), env, ctx);
  await done();
  assert.match(calls.at(-1).body, /move my bot role/);
});

test("scheduled: only brand-new role-less members get Unverified; bots get Bots", async () => {
  const now = Date.now();
  const iso = (msAgo) => new Date(now - msAgo).toISOString();
  mockDiscord({ members: [
    { user: { id: "1" }, roles: [], joined_at: iso(2 * 60e3) },          // new -> Unverified
    { user: { id: "2" }, roles: [], joined_at: iso(5 * 86400e3) },       // old -> untouched
    { user: { id: "3" }, roles: ["10"], joined_at: iso(60e3) },          // has role -> untouched
    { user: { id: "4", bot: true }, roles: [], joined_at: iso(60e3) },   // bot -> Bots
  ] });
  const { env } = await setup();
  const { ctx, done } = ctxFactory();
  await worker.scheduled({}, env, ctx);
  await done();
  const puts = calls.filter((c) => c.method === "PUT").map((c) => c.url.split("/members/")[1]);
  assert.deepEqual(puts.sort(), ["1/roles/11", "4/roles/12"]);
});
