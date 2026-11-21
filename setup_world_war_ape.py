#!/usr/bin/env python3
"""
World War Ape - Discord server setup bot (discord.py 2.x)

What it does
  * Creates roles, categories and channels (skips anything that already exists)
  * Sets permissions (verification, staff-only areas, read-only INFO channels)
  * Posts the verify button in the verify channel
  * Stays online afterwards so that:
        - new members automatically get "Unverified"
        - the verify button keeps working

It NEVER deletes anything. If something with the same name already exists it is
reused (category permissions are re-applied so they match this script).

Usage
    export DISCORD_BOT_TOKEN="your token"      # see README.md for Windows
    python setup_world_war_ape.py              # set up, then stay online
    python setup_world_war_ape.py --setup-only # set up, then exit

Optional: DISCORD_GUILD_ID = the server ID (only needed if the bot is in
more than one server).
"""

import os
import sys

import discord
from discord import PermissionOverwrite, Permissions

SEP = "・"  # the dot used in channel names:  📢・announcements


def ch(emoji: str, name: str) -> str:
    return f"{emoji}{SEP}{name}"


# --------------------------------------------------------------------------
# ROLES  (top -> bottom)  name, colour, hoisted (shown separately), permissions
# --------------------------------------------------------------------------
ADMIN_PERMS = Permissions(administrator=True)

HEAD_ADMIN_PERMS = Permissions(
    view_audit_log=True, manage_channels=True, kick_members=True, ban_members=True,
    manage_messages=True, moderate_members=True, manage_nicknames=True,
    manage_threads=True, mention_everyone=True, move_members=True,
    mute_members=True, deafen_members=True,
)
ADMIN_ROLE_PERMS = Permissions(
    view_audit_log=True, kick_members=True, ban_members=True,
    manage_messages=True, moderate_members=True, manage_nicknames=True,
    manage_threads=True, mention_everyone=True, move_members=True,
    mute_members=True,
)
# Moderators: manage messages, timeout, kick - and NO ban.
MOD_PERMS = Permissions(
    view_audit_log=True, kick_members=True, manage_messages=True,
    moderate_members=True, manage_nicknames=True, manage_threads=True,
    move_members=True, mute_members=True,
)
NONE = Permissions.none()

ROLES = [
    # name,               colour,   hoist, permissions
    ("Owner",             0xE74C3C, True,  ADMIN_PERMS),
    ("Co-Owner",          0xE67E22, True,  ADMIN_PERMS),
    ("Head Admin",        0xC0392B, True,  HEAD_ADMIN_PERMS),
    ("Admin",             0xD35400, True,  ADMIN_ROLE_PERMS),
    ("Head Moderator",    0x1ABC9C, True,  MOD_PERMS),
    ("Moderator",         0x2ECC71, True,  MOD_PERMS),
    ("Trial Moderator",   0x82E0AA, True,  MOD_PERMS),
    ("Lead Developer",    0x3498DB, True,  NONE),
    ("Developer",         0x5DADE2, True,  NONE),
    ("3D Modeler",        0x9B59B6, True,  NONE),
    ("Artist",            0xE91E63, True,  NONE),
    ("Music/Sound",       0xF39C12, True,  NONE),
    ("Community Manager", 0x16A085, True,  NONE),
    ("Playtester",        0xA3E635, True,  NONE),
    ("Supporter",         0xF1C40F, True,  NONE),
    ("Content Creator",   0xFF6B9D, True,  NONE),
    ("Verified",          0x95A5A6, False, NONE),
    ("Unverified",        0x546E7A, False, NONE),
    ("Bots",              0x7289DA, True,  NONE),
]
ROLE_NAMES = [r[0] for r in ROLES]

# --------------------------------------------------------------------------
# Who can do what
# --------------------------------------------------------------------------
TOP = ["Owner", "Co-Owner"]
ADMINS = TOP + ["Head Admin", "Admin"]
MODS = ADMINS + ["Head Moderator", "Moderator", "Trial Moderator"]
DEV = TOP + ["Lead Developer", "Developer", "3D Modeler", "Artist", "Music/Sound"]
# every role except Unverified can see the public channels
PUBLIC = [r for r in ROLE_NAMES if r != "Unverified"]
INFO_POSTERS = ADMINS  # Owner, Co-Owner, Head Admin, Admin

# --------------------------------------------------------------------------
# CATEGORIES AND CHANNELS
#   kind: verify | info | public | restricted
#   ("t", name) = text channel, ("v", name) = voice channel
# --------------------------------------------------------------------------
CATEGORIES = [
    {"name": "✅ VERIFY", "kind": "verify", "channels": [
        ("t", ch("✅", "verify")),
    ]},
    {"name": "📌 INFO", "kind": "info", "channels": [
        ("t", ch("📜", "rules")),
        ("t", ch("📢", "announcements")),
        ("t", ch("📰", "updates")),
        ("t", ch("🎉", "events")),
        ("t", ch("🔗", "links")),
    ]},
    {"name": "💬 COMMUNITY", "kind": "public", "channels": [
        ("t", ch("💬", "general")),
        ("t", ch("🖼️", "media")),
        ("t", ch("😂", "memes")),
        ("t", ch("💡", "suggestions")),
        ("t", ch("🎮", "looking-for-group")),
        ("t", ch("🤖", "bot-commands")),
    ]},
    {"name": "🐒 WORLD WAR APE", "kind": "public", "channels": [
        ("t", ch("🗺️", "game-info")),
        ("t", ch("🐛", "bug-reports")),
        ("t", ch("🧪", "playtesting")),
        ("t", ch("⭐", "showcase")),
    ]},
    {"name": "🔊 VOICE", "kind": "public", "channels": [
        ("v", ch("🔊", "General VC")),
        ("v", ch("🎮", "Gaming VC")),
        ("v", ch("🧪", "Playtest VC")),
    ]},
    {"name": "🛠️ DEV TEAM", "kind": "restricted", "roles": DEV, "channels": [
        ("t", ch("🛠️", "dev-chat")),
        ("t", ch("📋", "dev-updates")),
        ("t", ch("🐞", "dev-bugs")),
        ("t", ch("🎨", "art-and-models")),
        ("t", ch("🎵", "music-and-sound")),
        ("t", ch("💾", "builds")),
        ("v", ch("🔊", "Dev VC")),
    ]},
    {"name": "🛡️ MODERATION", "kind": "restricted", "roles": MODS, "channels": [
        ("t", ch("🛡️", "mod-chat")),
        ("t", ch("📝", "mod-logs")),
        ("t", ch("🚨", "reports")),
        ("t", ch("⚠️", "warnings")),
        ("v", ch("🔊", "Mod VC")),
    ]},
    {"name": "👑 ADMIN", "kind": "restricted", "roles": ADMINS, "channels": [
        ("t", ch("👑", "admin-chat")),
        ("t", ch("⚙️", "server-settings")),
        ("t", ch("📊", "admin-logs")),
        ("v", ch("🔊", "Admin VC")),
    ]},
]

REASON = "World War Ape server setup"


def norm(s: str) -> str:
    """Compare names ignoring case and emoji variation selectors."""
    return s.replace("️", "").strip().lower()


# --------------------------------------------------------------------------
# Verify button (persistent: keeps working after the bot restarts)
# --------------------------------------------------------------------------
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", emoji="✅", style=discord.ButtonStyle.success,
                       custom_id="wwa:verify")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild, member = interaction.guild, interaction.user
        verified = discord.utils.get(guild.roles, name="Verified")
        unverified = discord.utils.get(guild.roles, name="Unverified")
        if verified is None:
            await interaction.response.send_message(
                "The Verified role is missing - please tell an admin.", ephemeral=True)
            return
        if verified in member.roles:
            await interaction.response.send_message("You're already verified!", ephemeral=True)
            return
        try:
            await member.add_roles(verified, reason="Clicked verify button")
            if unverified in member.roles:
                await member.remove_roles(unverified, reason="Clicked verify button")
        except discord.Forbidden:
            await interaction.response.send_message(
                "I can't give you the role - an admin must move my bot role "
                "above Verified/Unverified.", ephemeral=True)
            return
        await interaction.response.send_message(
            "✅ You're verified! Welcome to World War Ape 🐒", ephemeral=True)


# --------------------------------------------------------------------------
# Permission builders
# --------------------------------------------------------------------------
def build_overwrites(guild, roles, spec):
    everyone = guild.default_role
    kind = spec["kind"]
    ow = {everyone: PermissionOverwrite(view_channel=False)}

    if kind == "verify":
        # Only Unverified can see it - read only, they just press the button.
        ow[roles["Unverified"]] = PermissionOverwrite(
            view_channel=True, read_message_history=True, send_messages=False,
            add_reactions=False, create_public_threads=False,
            create_private_threads=False, send_messages_in_threads=False)
        return ow

    for name in spec.get("roles", PUBLIC):
        ow[roles[name]] = PermissionOverwrite(view_channel=True)

    if kind == "info":
        # Read-only for everyone, except the posters.
        ow[everyone] = PermissionOverwrite(
            view_channel=False, send_messages=False, add_reactions=False,
            create_public_threads=False, create_private_threads=False,
            send_messages_in_threads=False)
        for name in INFO_POSTERS:
            ow[roles[name]] = PermissionOverwrite(
                view_channel=True, send_messages=True, add_reactions=True,
                create_public_threads=True, send_messages_in_threads=True)
    return ow


# --------------------------------------------------------------------------
# The bot
# --------------------------------------------------------------------------
class SetupBot(discord.Client):
    def __init__(self, setup_only: bool):
        intents = discord.Intents.default()
        intents.members = True  # privileged: enable "Server Members Intent" in the portal
        super().__init__(intents=intents)
        self.setup_only = setup_only
        self.did_setup = False
        self.created = []   # things created this run
        self.existing = []  # things that were already there
        self.notes = []     # warnings

    async def setup_hook(self):
        self.add_view(VerifyView())

    # ---- helpers ---------------------------------------------------------
    def pick_guild(self):
        gid = os.environ.get("DISCORD_GUILD_ID")
        if gid:
            return self.get_guild(int(gid))
        if len(self.guilds) == 1:
            return self.guilds[0]
        print("The bot is in several servers. Set DISCORD_GUILD_ID to one of:")
        for g in self.guilds:
            print(f"  {g.id}  {g.name}")
        return None

    # ---- roles -----------------------------------------------------------
    async def setup_roles(self, guild):
        roles = {}
        for name, colour, hoist, perms in ROLES:
            role = discord.utils.get(guild.roles, name=name)
            if role:
                self.existing.append(f"role {name}")
            else:
                role = await guild.create_role(
                    name=name, colour=discord.Colour(colour), hoist=hoist,
                    permissions=perms, mentionable=False, reason=REASON)
                self.created.append(f"role {name}")
            roles[name] = role

        # Put them in the right order (Owner on top ... Bots at the bottom).
        me = guild.get_member(self.user.id) or await guild.fetch_member(self.user.id)
        base = me.top_role.position
        movable = [roles[n] for n in ROLE_NAMES if roles[n] < me.top_role]
        if len(movable) < len(ROLE_NAMES):
            self.notes.append(
                "Some roles are at or above the bot's own role, so I couldn't reorder them. "
                "Drag the bot's role to the very top (below nothing), then run again.")
        if base - len(movable) < 1:
            self.notes.append(
                "The bot's role is too low to order all roles. Drag it to the top of the "
                "role list in Server Settings > Roles, then run the script again.")
        else:
            try:
                await guild.edit_role_positions(
                    {r: base - 1 - i for i, r in enumerate(movable)}, reason=REASON)
            except discord.HTTPException as e:
                self.notes.append(f"Couldn't reorder roles ({e}). Drag the bot's role to "
                                  "the top in Server Settings > Roles and run again.")
        return roles

    # ---- channels --------------------------------------------------------
    async def setup_channels(self, guild, roles):
        verify_channel = None
        for spec in CATEGORIES:
            overwrites = build_overwrites(guild, roles, spec)
            cat = next((c for c in guild.categories if norm(c.name) == norm(spec["name"])), None)
            if cat:
                await cat.edit(overwrites=overwrites, reason=REASON)
                self.existing.append(f"category {spec['name']} (permissions re-applied)")
            else:
                cat = await guild.create_category(spec["name"], overwrites=overwrites, reason=REASON)
                self.created.append(f"category {spec['name']}")

            for kind, name in spec["channels"]:
                found = next((c for c in cat.channels if norm(c.name) == norm(name)), None)
                if found:
                    self.existing.append(f"channel {name}")
                    channel = found
                else:
                    if kind == "t":
                        channel = await guild.create_text_channel(name, category=cat, reason=REASON)
                    else:
                        channel = await guild.create_voice_channel(name, category=cat, reason=REASON)
                    # make sure the new channel uses the category's permissions
                    await channel.edit(sync_permissions=True, reason=REASON)
                    self.created.append(f"{'text' if kind == 't' else 'voice'} channel {name}")
                if spec["kind"] == "verify":
                    verify_channel = channel
        return verify_channel

    # ---- verify message --------------------------------------------------
    async def post_verify_message(self, channel):
        async for msg in channel.history(limit=50):
            if msg.author.id == self.user.id and msg.components:
                self.existing.append("verify button message")
                return
        embed = discord.Embed(
            title="🐒 Welcome to World War Ape!",
            description=("Press the button below to verify and unlock the rest of the server.\n\n"
                         "By verifying you agree to follow the rules."),
            colour=discord.Colour(0x2ECC71))
        await channel.send(embed=embed, view=VerifyView())
        self.created.append("verify button message")

    # ---- main ------------------------------------------------------------
    async def on_ready(self):
        if self.did_setup:
            return
        self.did_setup = True
        try:
            guild = self.pick_guild()
            if guild is None:
                await self.close()
                return
            print(f"Setting up: {guild.name}")
            roles = await self.setup_roles(guild)
            verify_channel = await self.setup_channels(guild, roles)
            if verify_channel:
                await self.post_verify_message(verify_channel)
            # give the Bots role to bots already in the server
            for m in guild.members:
                if m.bot and roles["Bots"] not in m.roles:
                    try:
                        await m.add_roles(roles["Bots"], reason=REASON)
                    except discord.HTTPException:
                        pass
            self.print_report()
        except discord.Forbidden as e:
            print(f"\nPermission error: {e}\nDid you invite the bot with Administrator permission?")
            await self.close()
            return
        except Exception as e:  # noqa
            print(f"\nSomething went wrong: {e!r}")
            await self.close()
            return

        if self.setup_only:
            await self.close()
        else:
            print("\nBot is online. Leave this running so new members get 'Unverified' "
                  "and the verify button works. Press Ctrl+C to stop.")

    def print_report(self):
        print("\n=== CREATED ===")
        print("\n".join(f"  + {x}" for x in self.created) or "  (nothing new)")
        print("\n=== ALREADY EXISTED (kept, nothing deleted) ===")
        print("\n".join(f"  = {x}" for x in self.existing) or "  (none)")
        if self.notes:
            print("\n=== NOTES ===")
            print("\n".join(f"  ! {x}" for x in self.notes))

    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if member.bot:
            role = discord.utils.get(guild.roles, name="Bots")
        else:
            role = discord.utils.get(guild.roles, name="Unverified")
        if role:
            try:
                await member.add_roles(role, reason="Auto role on join")
            except discord.HTTPException as e:
                print(f"Couldn't give {role.name} to {member}: {e}")


def main():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        sys.exit("DISCORD_BOT_TOKEN is not set. See README.md, step 5.")
    bot = SetupBot(setup_only="--setup-only" in sys.argv)
    try:
        bot.run(token)
    except discord.LoginFailure:
        sys.exit("Login failed: the token is wrong. Reset it in the Developer Portal and try again.")
    except discord.PrivilegedIntentsRequired:
        sys.exit("Turn on 'Server Members Intent' in the Developer Portal (Bot tab), then run again.")


if __name__ == "__main__":
    main()
