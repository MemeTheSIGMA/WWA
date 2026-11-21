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
