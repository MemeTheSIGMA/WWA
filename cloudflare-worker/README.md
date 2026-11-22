# World War Ape – verification on Cloudflare Workers (24/7)

This moves the **Verify button** and the **auto-"Unverified" for new members** off your PC.
Nothing else changes: your server, roles, channels and the existing verify message stay as they are.

| Before (PC running the script)      | After (Cloudflare)                                              |
|-------------------------------------|-----------------------------------------------------------------|
| Button handled by the script        | Discord calls the Worker URL ("Interactions Endpoint")          |
| `on_member_join` gives Unverified   | A cron job runs **every minute** and gives Unverified to members who joined in the last 15 min and have no roles |

**One real difference:** a new member may wait up to about a minute before they get *Unverified* and see `✅・verify` (the old script was instant). Until then they see nothing. Existing members are never touched.

## Deploy (about 10 minutes, free plan is enough)

You need Node.js 18+ (<https://nodejs.org>) and a free Cloudflare account (<https://dash.cloudflare.com/sign-up>). Use any terminal; you only need it for these steps, and nothing has to stay open afterwards.

1. **Install** (inside this `cloudflare-worker` folder):
   ```
   npm install
   ```
2. **Fill in two values** in `wrangler.toml`:
   - `DISCORD_PUBLIC_KEY`: Developer Portal → your app → *General Information* → **Public Key** (this is public, not secret).
   - `DISCORD_GUILD_ID`: Discord → Settings → Advanced → Developer Mode ON, then right-click your server → *Copy Server ID*.
3. **Log in to Cloudflare:**
   ```
   npx wrangler login
   ```
4. **Deploy:**
   ```
   npx wrangler deploy
   ```
   It prints your URL, like `https://wwa-verify.<your-name>.workers.dev`.
5. **Store the bot token as a secret** (it asks you to paste it; it is encrypted and never shown again or put in a file):
   ```
   npx wrangler secret put DISCORD_BOT_TOKEN
   ```
6. **Tell Discord to use the Worker:** Developer Portal → your app → *General Information* → **Interactions Endpoint URL** → paste the Worker URL → Save.
   Discord sends a test request. If it saves with no error, the signature check works. If it says it couldn't verify the URL, the Public Key is wrong or the Worker isn't deployed.

## Test it (with the PC off)
1. Close PowerShell completely. Stop the old script if it's still running (Ctrl+C).
2. With a second Discord account, join the server (invite link).
3. Within ~1 minute it should get **Unverified** and see only `✅・verify`.
4. Click **Verify**. You should get a private "✅ You're verified!" reply, and the account now has **Verified** (not Unverified) and sees the public channels.

If it doesn't: `npx wrangler tail` shows live logs from the Worker.

## Important notes
- **Don't run the old script in its default mode anymore.** Use `python setup_world_war_ape.py --setup-only` if you ever need to re-create things. (If it runs too, it only gives double role-assignments, which is harmless, but pointless.)
- The existing verify button message keeps working; you do **not** need to repost it.
- The bot's role must still sit **above** Verified/Unverified/Bots (Server Settings → Roles).
- **Server Members Intent** must stay ON in the Developer Portal (the cron job lists members).
- Token safety: the token only lives as a Cloudflare secret. If it ever leaks, hit *Reset Token* in the portal and run step 5 again.
- Tests (no Discord/Cloudflare needed): `npm test`.
