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
      return reply(`Something went wrong verifying you (Discord said ${add.status}). Please try again or tell an admin.`);
    }
    if (unverified && member.roles?.includes(unverified)) {
      await discord(env, "DELETE", `/guilds/${guildId}/members/${uid}/roles/${unverified}`, undefined, "Clicked verify button");
    }
    return reply("✅ You're verified! Welcome to World War Ape 🐒");
  } catch (err) {
    console.error("verify failed", err);
    return reply(`Something went wrong verifying you (${String(err.message || err).slice(0, 80)}). Please try again or tell an admin.`);
  }
}


// ---------- applications (apply buttons -> form -> review channel -> Accept/Deny) ----------
const REVIEWERS = ["Owner", "Co-Owner", "Head Admin", "Admin"];
// [short label, full question, long answer?]
const APPS = {
  moderator: { label: "Moderator", emoji: "🛡️", role: "Trial Moderator", questions: [
    ["Timezone & active hours", "What is your timezone and what hours can you be active?", false],
    ["Past moderation experience", "Describe your past moderation experience.", true],
    ["Two members fighting in general?", "What would you do if two members start fighting in general?", true],
    ["A friend breaks the rules?", "How would you handle a friend breaking the rules?", true],
    ["Why do you want to moderate?", "Why do you want to moderate World War Ape?", true]] },
  developer: { label: "Developer", emoji: "💻", role: "Developer", questions: [
    ["Unity and C# experience", "What experience do you have with Unity and C#?", true],
    ["Multiplayer / Photon / VR experience", "What experience do you have with multiplayer, Photon or VR?", true],
    ["Link to past work or GitHub", "Link to your past work or GitHub.", false],
    ["Hours per week", "How many hours per week can you give?", false],
    ["Why do you want to join?", "Why do you want to join the dev team?", true]] },
  "3d_modeler": { label: "3D Modeler", emoji: "🧊", role: "3D Modeler", questions: [
    ["Software you use", "Which 3D software do you use?", false],
    ["Portfolio link", "Link to your portfolio.", false],
    ["Low-poly / Quest-friendly models", "Do you have experience with low-poly / Quest-friendly models?", true],
    ["Hours per week", "How many hours per week can you give?", false],
    ["Why do you want to join?", "Why do you want to join the team?", true]] },
  artist: { label: "Artist", emoji: "🎨", role: "Artist", questions: [
    ["Art style and tools", "What is your art style and which tools do you use?", true],
    ["Portfolio link", "Link to your portfolio.", false],
    ["Textures, UI or logos?", "Can you make textures, UI and/or logos? Which ones?", false],
    ["Hours per week", "How many hours per week can you give?", false],
    ["Why do you want to join?", "Why do you want to join the team?", true]] },
  music_sound: { label: "Music/Sound", emoji: "🎵", role: "Music/Sound", questions: [
    ["Tools you use", "Which tools do you use?", false],
    ["Link to samples", "Link to your samples.", false],
    ["Sound effects, music or both?", "Can you make sound effects, music, or both?", false],
    ["Hours per week", "How many hours per week can you give?", false],
    ["Why do you want to join?", "Why do you want to join the team?", true]] },
  playtester: { label: "Playtester", emoji: "🧪", role: "Playtester", questions: [
    ["VR headset you own", "Which VR headset do you own?", false],
    ["How often can you test?", "How often can you playtest?", false],
    ["Bug reporting experience", "Do you have experience reporting bugs? Tell us about it.", true],
    ["Favorite VR games", "What are your favorite VR games?", true],
    ["Why do you want to test?", "Why do you want to playtest World War Ape?", true]] },
  social_star: { label: "Social Star", emoji: "⭐", role: "⭐ Social Star Bronze", questions: [
    ["Platform(s) and channel links", "Which platform(s) do you create on? Include your channel links.", true],
    ["Follower count", "What is your follower count (per platform)?", false],
    ["How often do you post?", "How often do you post?", false],
    ["Content you'd make", "What content would you make about World War Ape?", true],
    ["Why do you want to join?", "Why do you want to be a Social Star?", true]] },
};

const ephemeral = (content) => json({ type: 4, data: { content, flags: EPHEMERAL } });
const normName = (n) => n.replace(/\uFE0F/g, "").trim().toLowerCase();

async function findChannel(env, guildId, suffix) {
  const res = await discord(env, "GET", `/guilds/${guildId}/channels`);
  if (!res.ok) throw new Error(`Couldn't read channels (${res.status})`);
  return (await res.json()).find((c) => c.type !== 4 && normName(c.name).endsWith(suffix));
}

async function dm(env, userId, content) {
  try {
    const c = await discord(env, "POST", "/users/@me/channels", { recipient_id: userId });
    if (!c.ok) return false;
    const m = await discord(env, "POST", `/channels/${(await c.json()).id}/messages`, { content });
    return m.ok;
  } catch (_) {
    return false;
  }
}

// Apply button -> open the form
async function handleApplyClick(interaction, env) {
  const key = interaction.data.custom_id.split(":")[2];
  const app = APPS[key];
  if (!app) return ephemeral("Unknown application type.");
  try {
    const roles = await getRoles(env, interaction.guild_id);
    if (roles[app.role] && interaction.member?.roles?.includes(roles[app.role]))
      return ephemeral(`You already have the **${app.role}** role.`);
  } catch (_) { /* fine - just show the form */ }
  return json({ type: 9, data: {
    custom_id: `wwa:form:${key}`,
    title: `${app.label} Application`.slice(0, 45),
    components: app.questions.map(([label, full, long], i) => ({
      type: 1, components: [{
        type: 4, custom_id: `q${i}`, label, placeholder: full.slice(0, 100),
        style: long ? 2 : 1, required: true, max_length: long ? 1000 : 300,
      }],
    })),
  } });
}

// Form submitted -> post to the review channel
async function handleFormSubmit(interaction, env) {
  const { guild_id: guildId, member, application_id: appId, token } = interaction;
  const key = interaction.data.custom_id.split(":")[2];
  const app = APPS[key];
  const reply = (content) =>
    fetch(`${API}/webhooks/${appId}/${token}/messages/@original`, {
      method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ content }),
    });
  try {
    const review = await findChannel(env, guildId, "application-review");
    if (!review) return reply("The review channel is missing - please tell an admin.");
    const user = member.user;
    const answers = {};
    for (const row of interaction.data.components) for (const c of row.components) answers[c.custom_id] = c.value;
    const embed = {
      title: `${app.emoji} ${app.label} Application`,
      color: 0xf1c40f,
      timestamp: new Date().toISOString(),
      author: { name: `${user.username} (${user.id})` },
      fields: [
        { name: "Applicant", value: `<@${user.id}>`, inline: false },
        ...app.questions.map(([, full], i) => ({
          name: full.slice(0, 256), value: (answers[`q${i}`] || "-").slice(0, 1024), inline: false,
        })),
      ],
      footer: { text: `app:${key}:${user.id}` },
    };
    const res = await discord(env, "POST", `/channels/${review.id}/messages`, {
      embeds: [embed],
      components: [{ type: 1, components: [
        { type: 2, style: 3, label: "Accept", emoji: { name: "✅" }, custom_id: `wwa:review:accept:${key}:${user.id}` },
        { type: 2, style: 4, label: "Deny", emoji: { name: "❌" }, custom_id: `wwa:review:deny:${key}:${user.id}` },
      ] }],
    });
    if (!res.ok) return reply(`Couldn't send your application (Discord said ${res.status}). Please tell an admin.`);
    return reply(`✅ Your **${app.label}** application was sent! We'll DM you with the result (keep your DMs open).`);
  } catch (err) {
    console.error("application failed", err);
    return reply("Something went wrong sending your application. Please try again or tell an admin.");
  }
}

// Accept / Deny pressed in the review channel
async function handleReview(interaction, env) {
  const { guild_id: guildId, member, application_id: appId, token, message } = interaction;
  const [, , action, key, uid] = interaction.data.custom_id.split(":");
  const app = APPS[key];
  const accepted = action === "accept";
  const followup = (content) =>
    fetch(`${API}/webhooks/${appId}/${token}`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ content, flags: EPHEMERAL }),
    });
  try {
    if (!app) return followup("Unknown application type.");
    const roles = await getRoles(env, guildId);
    const isAdmin = (BigInt(member.permissions || "0") & 8n) !== 0n;
    const isReviewer = isAdmin || REVIEWERS.some((n) => roles[n] && member.roles?.includes(roles[n]));
    if (!isReviewer) return followup("Only Owner, Co-Owner and Admins can review applications.");

    const reviewer = member.user.id;
    const notes = [];
    let inServer = true;
    if (accepted) {
      const roleId = roles[app.role];
      if (!roleId) return followup(`⚠️ The role **${app.role}** doesn't exist, so I did nothing. Create it and press Accept again.`);
      const add = await discord(env, "PUT", `/guilds/${guildId}/members/${uid}/roles/${roleId}`, undefined,
        `${app.label} application accepted`);
      if (add.status === 404) { inServer = false; notes.push("Applicant has left the server - no role given."); }
      else if (!add.ok) return followup(`⚠️ I can't give **${app.role}** (Discord said ${add.status}). Drag my bot role above it in Server Settings → Roles, then press Accept again.`);
    }
    const text = accepted
      ? `🎉 Congratulations! Your **${app.label}** application for **World War Ape** was accepted` +
        (inServer ? ` and you now have the **${app.role}** role.` : ".") + " Welcome to the team! 🐒"
      : `Hi! Thank you for applying for **${app.label}** in **World War Ape** and for the time you put in. ` +
        "After reviewing it, we're not able to accept your application right now. Please don't be " +
        "discouraged - you're welcome to apply again in the future. 💛";
    if (!(await dm(env, uid, text))) notes.push("Couldn't DM the applicant (their DMs are closed).");

    const embed = { ...(message.embeds?.[0] || {}) };
    embed.color = accepted ? 0x2ecc71 : 0xe74c3c;
    embed.fields = [...(embed.fields || []), {
      name: "Decision",
      value: `${accepted ? "✅ Accepted" : "❌ Denied"} by <@${reviewer}> • <t:${Math.floor(Date.now() / 1000)}:f>` +
        notes.map((n) => `\n⚠️ ${n}`).join(""),
      inline: false,
    }];
    await discord(env, "PATCH", `/channels/${message.channel_id}/messages/${message.id}`, { embeds: [embed], components: [] });

    const log = await findChannel(env, guildId, "admin-logs");
    if (log) {
      await discord(env, "POST", `/channels/${log.id}/messages`, {
        content: `${accepted ? "✅" : "❌"} <@${reviewer}> ${accepted ? "accepted" : "denied"} <@${uid}>'s **${app.label}** application.`,
        allowed_mentions: { parse: [] },
      });
    }
  } catch (err) {
    console.error("review failed", err);
    return followup(`Something went wrong (${String(err.message || err).slice(0, 80)}). Please try again.`);
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
    const id = interaction.data?.custom_id || "";
    if (interaction.type === 3 && id.startsWith("wwa:apply:")) return handleApplyClick(interaction, env);
    if (interaction.type === 5 && id.startsWith("wwa:form:")) {
      ctx.waitUntil(handleFormSubmit(interaction, env));
      return json({ type: 5, data: { flags: EPHEMERAL } });
    }
    if (interaction.type === 3 && id.startsWith("wwa:review:")) {
      ctx.waitUntil(handleReview(interaction, env));
      return json({ type: 6 });
    }
    return json({ type: 4, data: { content: "Unknown action.", flags: EPHEMERAL } });
  },

  async scheduled(_event, env, ctx) {
    ctx.waitUntil(assignJoinRoles(env));
  },
};
