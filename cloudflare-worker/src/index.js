/**
 * World War Ape - verification system on Cloudflare Workers
 *
 *  fetch()      Discord "Interactions Endpoint": handles the Verify button
 *               (custom_id "wwa:verify") -> gives Verified, removes Unverified.
 *  scheduled()  Runs every minute: gives "Unverified" to members who just joined
 *               (and "Bots" to bots), replacing the old on_member_join handler.
 *
 * Bindings (see wrangler.toml / README):
 *   DISCORD_PUBLIC_KEY  (var)    Developer Portal > General Information > Public Key
 *   DISCORD_GUILD_ID    (var)    your server's ID (used by the scheduled job)
 *   DISCORD_BOT_TOKEN   (secret) the bot token - set with `wrangler secret put`
 */

const API = "https://discord.com/api/v10";
const VERIFY_ID = "wwa:verify";
const EPHEMERAL = 64;
// Only members who joined within this window get Unverified automatically,
// so existing members are never touched.
const JOIN_WINDOW_MS = 15 * 60 * 1000;
const ROLE_CACHE_MS = 5 * 60 * 1000;
const REASON = "World War Ape verification";

// ---------- helpers ----------
const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });

function hexToBytes(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
  return out;
}

async function verifySignature(request, body, publicKey) {
  const sig = request.headers.get("X-Signature-Ed25519");
  const ts = request.headers.get("X-Signature-Timestamp");
  if (!sig || !ts || !publicKey) return false;
  const data = new TextEncoder().encode(ts + body);
  // "Ed25519" is the standard name; older runtimes used "NODE-ED25519".
  for (const alg of [{ name: "Ed25519" }, { name: "NODE-ED25519", namedCurve: "NODE-ED25519" }]) {
    try {
      const key = await crypto.subtle.importKey("raw", hexToBytes(publicKey), alg, false, ["verify"]);
      return await crypto.subtle.verify(alg.name, key, hexToBytes(sig), data);
    } catch (_) {
      /* try next algorithm name */
    }
  }
  return false;
}

async function discord(env, method, path, body, reason) {
  const headers = {
    Authorization: `Bot ${env.DISCORD_BOT_TOKEN}`,
    "User-Agent": "DiscordBot (wwa-verify-worker, 1.0)",
  };
  if (body !== undefined) headers["content-type"] = "application/json";
  if (reason) headers["X-Audit-Log-Reason"] = encodeURIComponent(reason);
  for (let attempt = 0; attempt < 3; attempt++) {
    const res = await fetch(`${API}${path}`, {
      method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (res.status === 429) {
      const wait = Number((await res.json().catch(() => ({}))).retry_after ?? 1);
      await new Promise((r) => setTimeout(r, Math.min(wait, 5) * 1000));
      continue;
    }
    return res;
  }
  throw new Error(`Discord rate limit on ${method} ${path}`);
}

// Look roles up by name, like the original bot did (cached per isolate).
let roleCache = { at: 0, guild: null, roles: {} };
async function getRoles(env, guildId) {
  if (roleCache.guild === guildId && Date.now() - roleCache.at < ROLE_CACHE_MS) return roleCache.roles;
  const res = await discord(env, "GET", `/guilds/${guildId}/roles`);
  if (!res.ok) throw new Error(`Couldn't read roles (${res.status})`);
  const roles = {};
  for (const r of await res.json()) roles[r.name] ??= r.id;
  roleCache = { at: Date.now(), guild: guildId, roles };
  return roles;
}

// ---------- button click ----------
async function handleVerify(interaction, env) {
  const { guild_id: guildId, member, application_id: appId, token } = interaction;
  const reply = (content) =>
    fetch(`${API}/webhooks/${appId}/${token}/messages/@original`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ content }),
    });

  try {
    if (!guildId || !member?.user) return reply("This button only works inside the server.");
    const roles = await getRoles(env, guildId);
    const verified = roles["Verified"];
    const unverified = roles["Unverified"];
    if (!verified) return reply("The Verified role is missing - please tell an admin.");
    if (member.roles?.includes(verified)) return reply("You're already verified!");

    const uid = member.user.id;
    const add = await discord(env, "PUT", `/guilds/${guildId}/members/${uid}/roles/${verified}`, undefined, "Clicked verify button");
    if (!add.ok) {
      if (add.status === 403) {
        return reply("I can't give you the role - an admin must move my bot role above Verified/Unverified.");
      }
      return reply("Something went wrong verifying you. Please try again or tell an admin.");
    }
    if (unverified && member.roles?.includes(unverified)) {
      await discord(env, "DELETE", `/guilds/${guildId}/members/${uid}/roles/${unverified}`, undefined, "Clicked verify button");
    }
    return reply("✅ You're verified! Welcome to World War Ape 🐒");
  } catch (err) {
    console.error("verify failed", err);
    return reply("Something went wrong verifying you. Please try again or tell an admin.");
  }
}

// ---------- scheduled: auto roles for new members ----------
async function assignJoinRoles(env) {
  const guildId = env.DISCORD_GUILD_ID;
  if (!guildId) return console.warn("DISCORD_GUILD_ID not set - skipping join-role check");
  const roles = await getRoles(env, guildId);
  const cutoff = Date.now() - JOIN_WINDOW_MS;

  let after = "0";
  for (let page = 0; page < 20; page++) {
    const res = await discord(env, "GET", `/guilds/${guildId}/members?limit=1000&after=${after}`);
    if (!res.ok) throw new Error(`Couldn't list members (${res.status}) - is Server Members Intent on?`);
    const members = await res.json();
    for (const m of members) {
      if (!m.joined_at || Date.parse(m.joined_at) < cutoff) continue;
      const wantsRole = m.user.bot ? roles["Bots"] : roles["Unverified"];
      // Only brand-new members with no roles at all (not already verified/handled).
      if (!wantsRole || m.roles.length > 0) continue;
      const r = await discord(env, "PUT", `/guilds/${guildId}/members/${m.user.id}/roles/${wantsRole}`, undefined, "Auto role on join");
      if (!r.ok) console.warn(`Couldn't give role to ${m.user.id}: ${r.status}`);
    }
    if (members.length < 1000) break;
    after = members[members.length - 1].user.id;
  }
}

// ---------- entry points ----------
export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") return new Response("World War Ape verification worker is running.");
    const body = await request.text();
    if (!(await verifySignature(request, body, env.DISCORD_PUBLIC_KEY))) {
      return new Response("invalid request signature", { status: 401 });
    }
    const interaction = JSON.parse(body);

    if (interaction.type === 1) return json({ type: 1 }); // PING

    if (interaction.type === 3 && interaction.data?.custom_id === VERIFY_ID) {
      // Acknowledge instantly (Discord needs a reply in 3s), do the work after.
      ctx.waitUntil(handleVerify(interaction, env));
      return json({ type: 5, data: { flags: EPHEMERAL } });
    }
    return json({ type: 4, data: { content: "Unknown action.", flags: EPHEMERAL } });
  },

  async scheduled(_event, env, ctx) {
    ctx.waitUntil(assignJoinRoles(env));
  },
};
