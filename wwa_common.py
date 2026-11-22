"""Small helpers shared by the World War Ape bot modules."""

import discord

SEP = "・"  # the dot used in channel names:  📢・announcements


def ch(emoji: str, name: str) -> str:
    return f"{emoji}{SEP}{name}"


def norm(s: str) -> str:
    """Compare names ignoring case and emoji variation selectors."""
    return s.replace("️", "").strip().lower()


def find_channel(guild: discord.Guild, name: str):
    """Find a (non-category) channel by its display name."""
    n = norm(name)
    for c in guild.channels:
        if not isinstance(c, discord.CategoryChannel) and norm(c.name) == n:
            return c
    return None


async def upsert_embed(channel, me_id: int, marker: str, embed: discord.Embed, view=None):
    """Post an embed, or edit the bot's existing one (found by its footer text)."""
    embed.set_footer(text=marker)
    async for m in channel.history(limit=50):
        if (m.author.id == me_id and m.embeds and m.embeds[0].footer
                and m.embeds[0].footer.text == marker):
            await m.edit(embed=embed, view=view)
            return "updated"
    await channel.send(embed=embed, view=view)
    return "created"
