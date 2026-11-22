"""Social Star tiers. EDIT THE TEXT BELOW, then run the bot again:
it updates the message in 📜・social-star-info for you."""

import discord

BRONZE = "⭐ Social Star Bronze"
SILVER = "⭐ Social Star Silver"
GOLD = "⭐ Social Star Gold"
PLATINUM = "💎 Social Star Platinum"
SOCIAL_ROLES_TOP_DOWN = [PLATINUM, GOLD, SILVER, BRONZE]

INFO_MARKER = "World War Ape • Social Stars"

# (title, requirements, what it unlocks)  <- edit freely
TIERS = [
    (BRONZE + " (Level 1)",
     "**Requirements:** [EDIT ME - e.g. 100+ followers]",
     "Access to the 🌟 SOCIAL STARS category: promote your content, "
     "Social Star chat and clip sharing."),
    (SILVER + " (Level 2)",
     "**Requirements:** [EDIT ME - e.g. 500+ followers]",
     "Everything in Bronze, plus [EDIT ME - Silver perks]."),
    (GOLD + " (Level 3)",
     "**Requirements:** [EDIT ME - e.g. 2,000+ followers]",
     "Everything in Silver, plus the 🏆・gold-plus-perks channel."),
    (PLATINUM + " (Legendary)",
     "**Requirements:** [EDIT ME - e.g. 10,000+ followers / invite only]",
     "Everything in Gold, plus the 💎 PLATINUM LOUNGE: early access content, "
     "dev collabs, announcements and a private voice channel."),
]


def info_embed() -> discord.Embed:
    e = discord.Embed(
        title="🌟 World War Ape - Social Stars",
        description=("Content creators who support World War Ape can earn a Social Star tier. "
                     "Apply in 📋・apply-here (Social Star application)."),
        colour=discord.Colour(0xFFC300))
    for title, req, unlocks in TIERS:
        e.add_field(name=title, value=f"{req}\n**Unlocks:** {unlocks}", inline=False)
    return e
