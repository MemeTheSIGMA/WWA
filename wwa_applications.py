"""
Applications system (buttons -> modal forms -> review channel with Accept/Deny).

Everything survives restarts:
  * the apply buttons are a persistent view (fixed custom_ids)
  * Accept/Deny buttons are "dynamic items" whose custom_id carries the
    application type and the applicant's ID, so no database is needed
  * pending applications are re-discovered from the review channel at startup
"""

import re

import discord

from wwa_common import ch, find_channel, upsert_embed

APPLY_CHANNEL = ch("📋", "apply-here")
REVIEW_CHANNEL = ch("📥", "application-review")
LOG_CHANNEL = ch("📊", "admin-logs")
REVIEWERS = ["Owner", "Co-Owner", "Head Admin", "Admin"]
APPLY_MARKER = "World War Ape • Applications"

# key -> label, emoji, role given on Accept, questions
# question = (short label [max 45 chars], full question [max 100 chars], long answer?)
# NOTE: Discord allows at most 5 questions per form.
APPS = {
    "moderator": {
        "label": "Moderator", "emoji": "🛡️",
        "role": "Trial Moderator",  # <- change to "Moderator" if you want applicants to start there
        "questions": [
            ("Timezone & active hours", "What is your timezone and what hours can you be active?", False),
            ("Past moderation experience", "Describe your past moderation experience.", True),
            ("Two members fighting in general?", "What would you do if two members start fighting in general?", True),
            ("A friend breaks the rules?", "How would you handle a friend breaking the rules?", True),
            ("Why do you want to moderate?", "Why do you want to moderate World War Ape?", True),
        ],
    },
    "developer": {
        "label": "Developer", "emoji": "💻", "role": "Developer",
        "questions": [
            ("Unity and C# experience", "What experience do you have with Unity and C#?", True),
            ("Multiplayer / Photon / VR experience", "What experience do you have with multiplayer, Photon or VR?", True),
            ("Link to past work or GitHub", "Link to your past work or GitHub.", False),
            ("Hours per week", "How many hours per week can you give?", False),
            ("Why do you want to join?", "Why do you want to join the dev team?", True),
        ],
    },
    "3d_modeler": {
        "label": "3D Modeler", "emoji": "🧊", "role": "3D Modeler",
        "questions": [
            ("Software you use", "Which 3D software do you use?", False),
            ("Portfolio link", "Link to your portfolio.", False),
            ("Low-poly / Quest-friendly models", "Do you have experience with low-poly / Quest-friendly models?", True),
            ("Hours per week", "How many hours per week can you give?", False),
            ("Why do you want to join?", "Why do you want to join the team?", True),
        ],
    },
    "artist": {
        "label": "Artist", "emoji": "🎨", "role": "Artist",
        "questions": [
            ("Art style and tools", "What is your art style and which tools do you use?", True),
            ("Portfolio link", "Link to your portfolio.", False),
            ("Textures, UI or logos?", "Can you make textures, UI and/or logos? Which ones?", False),
            ("Hours per week", "How many hours per week can you give?", False),
            ("Why do you want to join?", "Why do you want to join the team?", True),
        ],
    },
    "music_sound": {
        "label": "Music/Sound", "emoji": "🎵", "role": "Music/Sound",
        "questions": [
            ("Tools you use", "Which tools do you use?", False),
            ("Link to samples", "Link to your samples.", False),
            ("Sound effects, music or both?", "Can you make sound effects, music, or both?", False),
            ("Hours per week", "How many hours per week can you give?", False),
            ("Why do you want to join?", "Why do you want to join the team?", True),
        ],
    },
    "playtester": {
        "label": "Playtester", "emoji": "🧪", "role": "Playtester",
        "questions": [
            ("VR headset you own", "Which VR headset do you own?", False),
            ("How often can you test?", "How often can you playtest?", False),
            ("Bug reporting experience", "Do you have experience reporting bugs? Tell us about it.", True),
            ("Favorite VR games", "What are your favorite VR games?", True),
            ("Why do you want to test?", "Why do you want to playtest World War Ape?", True),
        ],
    },
    "social_star": {
        "label": "Social Star", "emoji": "⭐", "role": "⭐ Social Star Bronze",
        "questions": [
            ("Platform(s) and channel links", "Which platform(s) do you create on? Include your channel links.", True),
            ("Follower count", "What is your follower count (per platform)?", False),
            ("How often do you post?", "How often do you post?", False),
            ("Content you'd make", "What content would you make about World War Ape?", True),
            ("Why do you want to join?", "Why do you want to be a Social Star?", True),
        ],
    },
}

# Discord's limits - checked when the module loads so a typo fails early.
for _k, _a in APPS.items():
    assert re.fullmatch(r"[a-z0-9_]+", _k)
    assert len(_a["questions"]) <= 5, _k
    assert len(f"{_a['label']} Application") <= 45, _k
    for _label, _full, _long in _a["questions"]:
        assert len(_label) <= 45, _label
        assert len(_full) <= 100, _full

# (user_id, key) of applications waiting for a decision. Rebuilt at startup.
PENDING = set()


def is_reviewer(member) -> bool:
    return (member.guild_permissions.administrator
            or any(r.name in REVIEWERS for r in member.roles))


async def try_dm(user, content: str) -> bool:
    try:
        await user.send(content)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


_FOOTER = re.compile(r"^app:([a-z0-9_]+):(\d+)$")


async def load_pending(guild, me_id: int):
    """Re-discover pending applications (review messages that still have buttons)."""
    PENDING.clear()
    review = find_channel(guild, REVIEW_CHANNEL)
    if review is None:
        return
    async for m in review.history(limit=1000):
        if m.author.id != me_id or not m.embeds or not m.components:
            continue
        foot = m.embeds[0].footer.text if m.embeds[0].footer else ""
        hit = _FOOTER.match(foot or "")
        if hit:
            PENDING.add((int(hit.group(2)), hit.group(1)))


# --------------------------------------------------------------------------
# Review buttons (Accept / Deny) - persistent via DynamicItem
# --------------------------------------------------------------------------
class ReviewButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"wwa:review:(?P<action>accept|deny):(?P<key>[a-z0-9_]+):(?P<uid>[0-9]+)",
):
    def __init__(self, action: str, key: str, uid: int):
        accept = action == "accept"
        super().__init__(discord.ui.Button(
            label="Accept" if accept else "Deny",
            emoji="✅" if accept else "❌",
            style=discord.ButtonStyle.success if accept else discord.ButtonStyle.danger,
            custom_id=f"wwa:review:{action}:{key}:{uid}",
        ))
        self.action, self.key, self.uid = action, key, uid

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(match["action"], match["key"], int(match["uid"]))

    async def callback(self, interaction: discord.Interaction):
        guild, reviewer = interaction.guild, interaction.user
        if not is_reviewer(reviewer):
            await interaction.response.send_message(
                "Only Owner, Co-Owner and Admins can review applications.", ephemeral=True)
            return
        app = APPS.get(self.key)
        if app is None:
            await interaction.response.send_message("Unknown application type.", ephemeral=True)
            return
        await interaction.response.defer()

        accepted = self.action == "accept"
        applicant = guild.get_member(self.uid)
        if applicant is None:
            try:
                applicant = await guild.fetch_member(self.uid)
            except discord.NotFound:
                applicant = None

        notes = []
        if accepted and applicant is not None:
            role = discord.utils.get(guild.roles, name=app["role"])
            if role is None:
                await interaction.followup.send(
                    f"⚠️ The role **{app['role']}** doesn't exist, so I did nothing. "
                    "Create it (or run the setup again) and press Accept again.", ephemeral=True)
                return
            try:
                await applicant.add_roles(role, reason=f"{app['label']} application accepted by {reviewer}")
            except discord.Forbidden:
                await interaction.followup.send(
                    f"⚠️ I can't give **{role.name}**. Drag my bot role above it in "
                    "Server Settings → Roles, then press Accept again.", ephemeral=True)
                return
        elif accepted:
            notes.append("Applicant has left the server - no role given.")

        # DM the applicant
        try:
            target = applicant or await interaction.client.fetch_user(self.uid)
        except discord.HTTPException:
            target = None
        if target is not None:
            if accepted:
                text = (f"🎉 Congratulations! Your **{app['label']}** application for "
                        f"**World War Ape** was accepted"
                        + (f" and you now have the **{app['role']}** role." if applicant else ".")
                        + " Welcome to the team! 🐒")
            else:
                text = (f"Hi! Thank you for applying for **{app['label']}** in **World War Ape** "
                        "and for the time you put in. After reviewing it, we're not able to "
                        "accept your application right now. Please don't be discouraged - "
                        "you're welcome to apply again in the future. 💛")
            if not await try_dm(target, text):
                notes.append("Couldn't DM the applicant (their DMs are closed).")

        # Update the review message: remove buttons, record who decided
        embed = discord.Embed.from_dict(interaction.message.embeds[0].to_dict())
        embed.colour = discord.Colour.green() if accepted else discord.Colour.red()
        verdict = "✅ Accepted" if accepted else "❌ Denied"
        value = f"{verdict} by {reviewer.mention} • {discord.utils.format_dt(discord.utils.utcnow(), 'f')}"
        if notes:
            value += "\n" + "\n".join(f"⚠️ {n}" for n in notes)
        embed.add_field(name="Decision", value=value, inline=False)
        await interaction.edit_original_response(embed=embed, view=None)
        PENDING.discard((self.uid, self.key))

        # Log it
        log = find_channel(guild, LOG_CHANNEL)
        if log is not None:
            try:
                await log.send(
                    f"{'✅' if accepted else '❌'} {reviewer.mention} "
                    f"{'accepted' if accepted else 'denied'} <@{self.uid}>'s **{app['label']}** application.",
                    allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                pass


def review_view(key: str, uid: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(ReviewButton("accept", key, uid))
    view.add_item(ReviewButton("deny", key, uid))
    return view


# --------------------------------------------------------------------------
# The form (modal)
# --------------------------------------------------------------------------
class ApplicationModal(discord.ui.Modal):
    def __init__(self, key: str):
        app = APPS[key]
        super().__init__(title=f"{app['label']} Application")
        self.key = key
        self.inputs = []
        for label, full, long in app["questions"]:
            ti = discord.ui.TextInput(
                label=label, placeholder=full,
                style=discord.TextStyle.paragraph if long else discord.TextStyle.short,
                required=True, max_length=1000 if long else 300)
            self.inputs.append(ti)
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction):
        app, user, guild = APPS[self.key], interaction.user, interaction.guild
        marker = (user.id, self.key)
        review = find_channel(guild, REVIEW_CHANNEL)
        if review is None:
            await interaction.response.send_message(
                "The review channel is missing - please tell an admin.", ephemeral=True)
            return
        if marker in PENDING:  # e.g. double submit
            await interaction.response.send_message(
                f"You already have a pending **{app['label']}** application.", ephemeral=True)
            return
        PENDING.add(marker)
        try:
            embed = discord.Embed(
                title=f"{app['emoji']} {app['label']} Application",
                colour=discord.Colour.gold(), timestamp=discord.utils.utcnow())
            embed.set_author(name=f"{user} ({user.id})", icon_url=user.display_avatar.url)
            embed.add_field(
                name="Applicant",
                value=(f"{user.mention}\nAccount created: {discord.utils.format_dt(user.created_at, 'R')}"
                       + (f"\nJoined server: {discord.utils.format_dt(user.joined_at, 'R')}"
                          if user.joined_at else "")),
                inline=False)
            for (label, full, long), ti in zip(app["questions"], self.inputs):
                embed.add_field(name=full[:256], value=(ti.value or "-")[:1024], inline=False)
            embed.set_footer(text=f"app:{self.key}:{user.id}")
            await review.send(embed=embed, view=review_view(self.key, user.id))
        except Exception:
            PENDING.discard(marker)
            raise
        await interaction.response.send_message(
            f"✅ Your **{app['label']}** application was sent! We'll DM you with the result "
            "(keep your DMs open).", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Application form error: {error!r}")
        msg = "Something went wrong sending your application. Please try again or tell an admin."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


# --------------------------------------------------------------------------
# The apply buttons (one message, one button per application)
# --------------------------------------------------------------------------
class ApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for key, app in APPS.items():
            btn = discord.ui.Button(
                label=app["label"], emoji=app["emoji"],
                style=discord.ButtonStyle.primary, custom_id=f"wwa:apply:{key}")
            btn.callback = self._make_callback(key)
            self.add_item(btn)

    @staticmethod
    def _make_callback(key: str):
        async def callback(interaction: discord.Interaction):
            app, member = APPS[key], interaction.user
            role = discord.utils.get(interaction.guild.roles, name=app["role"])
            if role is not None and role in member.roles:
                await interaction.response.send_message(
                    f"You already have the **{role.name}** role.", ephemeral=True)
                return
            if (member.id, key) in PENDING:
                await interaction.response.send_message(
                    f"You already have a pending **{app['label']}** application. "
                    "Please wait for a reply before applying again.", ephemeral=True)
                return
            await interaction.response.send_modal(ApplicationModal(key))
        return callback


async def post_apply_message(channel, me_id: int) -> str:
    lines = [f"{a['emoji']} **{a['label']}**" for a in APPS.values()]
    embed = discord.Embed(
        title="📝 Apply for World War Ape",
        description=("Want to help build World War Ape? Press a button below, fill in the form, "
                     "and our team will review it. You'll get a DM with the result.\n\n"
                     + "\n".join(lines)
                     + "\n\n*You can only have one pending application per role at a time.*"),
        colour=discord.Colour(0x2ECC71))
    return await upsert_embed(channel, me_id, APPLY_MARKER, embed, view=ApplyView())
