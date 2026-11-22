# World War Ape – Discord server setup

`setup_world_war_ape.py` builds your whole server (roles, categories, channels,
permissions, verify button) using **your own bot**. It never deletes anything:
if a role/channel with the same name exists, it is kept.

## 1. Create the server
In Discord press the **+** on the left → *Create My Own* → name it *World War Ape*.

## 2. Create the bot
1. Go to <https://discord.com/developers/applications> and log in.
2. **New Application** → name it (e.g. "WWA Bot") → Create.
3. Open the **Bot** tab on the left.
4. Scroll to **Privileged Gateway Intents** and turn **Server Members Intent** ON → Save.
   (Needed so the bot can give "Unverified" to new members.)
5. At the top of the Bot tab click **Reset Token** → copy the token.
   Treat it like a password. Never paste it into the script or share it.
   If it ever leaks, press Reset Token again.

## 3. Invite the bot with Administrator
1. **OAuth2 → URL Generator**.
2. Scopes: tick **bot**.
3. Bot Permissions: tick **Administrator**.
4. Open the generated URL at the bottom, choose your server, Authorize.

## 4. Install Python and discord.py
1. Install Python 3.9+ from <https://python.org> (on Windows tick "Add Python to PATH").
2. In a terminal, go to this folder and run:
   ```
   pip install -r requirements.txt
   ```
   (on Mac/Linux you may need `pip3`)

## 5. Give the script your token (environment variable)
- **Mac / Linux:** `export DISCORD_BOT_TOKEN="paste-token-here"`
- **Windows PowerShell:** `$env:DISCORD_BOT_TOKEN="paste-token-here"`
- **Windows cmd:** `set DISCORD_BOT_TOKEN=paste-token-here`

This only lasts for that terminal window. Run step 6 in the same window.

## 6. Run it
```
python setup_world_war_ape.py
```
It prints what it created. Then it **stays online** – leave it running so new
members automatically get *Unverified* and the verify button works.
Press Ctrl+C to stop. To only build and quit: `python setup_world_war_ape.py --setup-only`.
It's safe to re-run any time (it skips what exists and re-applies category permissions).

If the bot is in more than one server, also set `DISCORD_GUILD_ID` to the server's ID
(Discord → Settings → Advanced → Developer Mode on, then right-click the server → Copy Server ID).

## What you still do by hand
1. **Give yourself the Owner role** (Server Settings → Members/Roles). The bot doesn't assign staff roles. Do the same for staff.
   Give staff the *Verified* role too, so they see the public channels (or they can click the button).
2. **Check the role order:** Server Settings → Roles. The bot's own role should be at the very top. If the script printed a note about this, drag it up and re-run.
3. **Fill in content:** rules text in 📜・rules, links, first announcement, game info.
4. **Existing members** don't get *Unverified* automatically. Only new joiners do. Give existing members *Verified* (or Unverified) yourself.
5. **Keep the bot running** (it must be online to assign Unverified on join and to handle the button). Your PC works; for 24/7 use a cheap host/VPS or a Raspberry Pi. If the bot is offline, new joiners see nothing until it's back.
6. Optional: turn on **Community** features (Server Settings → Enable Community) and set 📜・rules / 📢・announcements as rules and updates channels; set the server icon; add a welcome message; consider a logging bot to fill 📝・mod-logs, 📊・admin-logs.
7. Permission notes you may want to tweak: Owner & Co-Owner get the Administrator permission; Trial Moderators have the same powers as Moderators (manage messages, timeout, kick, no ban); only Head Admin/Admin can ban. Developer-type roles have no extra server powers.

---

# New: Applications, Social Stars and Welcome cards

Run the same script again (`pip install -r requirements.txt` first, it now also needs **Pillow**):
```
python setup_world_war_ape.py
```
It only adds the new things and skips what already exists.

**Added:** `👋 WELCOME`, `📝 APPLICATIONS` (apply buttons + private review channel), `🌟 SOCIAL STARS`, `💎 PLATINUM LOUNGE`, and 4 Social Star roles (Bronze < Silver < Gold < Platinum) above Verified.

## Important: do NOT use the Cloudflare Worker with this
Discord sends **all** button clicks to the "Interactions Endpoint URL" if one is set. If you ever set it (Developer Portal → General Information), the application buttons stop working. **Leave that box empty** (clear it if it isn't). The `cloudflare-worker/` folder can be ignored; this bot now does verification itself.

## Turn on the Server Members intent (needed for join detection + welcome cards)
1. <https://discord.com/developers/applications> → your app → **Bot** tab.
2. Scroll to **Privileged Gateway Intents**.
3. Switch **Server Members Intent** ON → **Save Changes**.

## Keep it online 24/7
The bot only works while the script is running.
- **Easiest:** leave it running on a PC that stays on (turn off sleep). Closing the window stops it.
- **Proper:** rent a tiny always-on host (a ~$5/month VPS, or a bot host such as Railway/Render). Upload this folder, run `pip install -r requirements.txt`, set the environment variable `DISCORD_BOT_TOKEN`, and set the start command to `python setup_world_war_ape.py`. Use the host's "always restart" option. Buttons keep working after restarts (they're persistent).

## Notes
- **Accept roles:** Moderator → **Trial Moderator** (safer start; change `"role"` in `wwa_applications.py` to `"Moderator"` if you want), Developer → Developer, 3D Modeler, Artist, Music/Sound, Playtester → same-named roles, Social Star → **⭐ Social Star Bronze**. Only Owner/Co-Owner/Admins can press Accept/Deny; the decision and who made it is saved on the review message and logged in `📊・admin-logs`.
- Pending applications survive restarts. After Accept/Deny the person can apply again.
- **Edit Social Star tiers:** change the text in `wwa_social.py`, run the script again; it updates the message.
- **Welcome channel:** visible to everyone, including people still Unverified, so they see the "go verify" message (set `WELCOME_VISIBLE_TO_UNVERIFIED = False` in the script to change). Nobody can type there, except people with the Administrator permission (Owner/Co-Owner), because Discord never blocks admins.
- Custom font for the welcome card: put a bold `.ttf` at `assets/font.ttf`.
- The bot's role must stay **above** every role it hands out (Server Settings → Roles).
