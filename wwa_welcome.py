"""Welcome card: a Pillow-drawn image posted in 👋・welcome when someone joins."""

import asyncio
import io
import random
from pathlib import Path

import discord
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from wwa_common import ch, find_channel

WELCOME_CHANNEL = ch("👋", "welcome")
VERIFY_CHANNEL = ch("✅", "verify")
RULES_CHANNEL = ch("📜", "rules")

W, H = 1000, 450

# Put your own bold font at  assets/font.ttf  to override these.
_FONT_CANDIDATES = [
    Path(__file__).parent / "assets" / "font.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _font(size: int):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def _background(rng: random.Random) -> Image.Image:
    # dark gradient
    img = Image.new("RGB", (W, H))
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        px.line([(0, y), (W, y)], fill=(int(16 + 30 * t), int(18 + 16 * t), int(14 + 6 * t)))
    img = img.convert("RGBA")

    # fire glow on the horizon
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse((W * 0.1, H * 0.72, W * 0.9, H * 1.35), fill=130)
    mask = mask.filter(ImageFilter.GaussianBlur(70))
    img = Image.composite(Image.new("RGBA", (W, H), (255, 92, 20, 255)), img, mask)

    # drifting smoke
    smoke = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(smoke)
    for _ in range(8):
        x, y, r = rng.randint(-50, W), rng.randint(0, H), rng.randint(60, 170)
        sd.ellipse((x - r, y - r // 2, x + r, y + r // 2), fill=(130, 130, 125, 38))
    img = Image.alpha_composite(img, smoke.filter(ImageFilter.GaussianBlur(40)))

    # ruined skyline
    sky = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pts, x = [(0, H)], 0
    while x < W:
        w, top = rng.randint(30, 80), H - rng.randint(35, 115)
        pts += [(x, top), (x + w * 0.5, top - rng.randint(0, 18)), (x + w, top + rng.randint(0, 25))]
        x += w
    pts.append((W, H))
    ImageDraw.Draw(sky).polygon(pts, fill=(6, 6, 6, 255))
    img = Image.alpha_composite(img, sky)

    # film grain
    noise = Image.effect_noise((W, H), 48)
    img = Image.blend(img, Image.merge("RGBA", (noise, noise, noise, Image.new("L", (W, H), 255))), 0.08)

    # scratches
    scr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scr)
    for _ in range(40):
        x1, y1 = rng.randint(0, W), rng.randint(0, H)
        sd.line((x1, y1, x1 + rng.randint(-120, 120), y1 + rng.randint(-40, 40)),
                fill=(205, 205, 195, rng.randint(15, 45)), width=1)
    img = Image.alpha_composite(img, scr)

    # vignette
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.2, -H * 0.3, W * 1.2, H * 1.3), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    img = Image.composite(img, Image.new("RGBA", (W, H), (0, 0, 0, 255)), vig)

    # thin frame
    ImageDraw.Draw(img).rectangle((10, 10, W - 11, H - 11), outline=(140, 45, 20, 255), width=3)
    return img


def _circle_avatar(avatar_bytes, size: int, letter: str) -> Image.Image:
    try:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        av = Image.new("RGBA", (size, size), (60, 60, 55, 255))
        d = ImageDraw.Draw(av)
        f = _font(size // 2)
        bb = d.textbbox((0, 0), letter, font=f)
        d.text(((size - (bb[2] - bb[0])) / 2 - bb[0], (size - (bb[3] - bb[1])) / 2 - bb[1]),
               letter, font=f, fill=(230, 230, 220))
    big = Image.new("L", (size * 4, size * 4), 0)  # supersampled for smooth edges
    ImageDraw.Draw(big).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    av.putalpha(ImageChops.multiply(big.resize((size, size), Image.LANCZOS), av.getchannel("A")))
    return av


def _centered(draw, text, cy, font, fill, stroke=3):
    bb = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    x = (W - (bb[2] - bb[0])) / 2 - bb[0]
    y = cy - (bb[3] - bb[1]) / 2 - bb[1]
    draw.text((x + 3, y + 4), text, font=font, fill=(0, 0, 0, 210), stroke_width=stroke, stroke_fill=(0, 0, 0, 210))
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))


def make_welcome_card(avatar_bytes, username: str, member_number: int) -> io.BytesIO:
    rng = random.Random(member_number)
    img = _background(rng)

    size = 210
    left, top = (W - size) // 2, 28
    ring = (left - 7, top - 7, left + size + 7, top + size + 7)

    # glowing border
    for width, blur in ((22, 22), (14, 10)):
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse(ring, outline=(255, 110, 20, 255), width=width)
        img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(blur)))
    crisp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(crisp).ellipse(ring, outline=(255, 175, 60, 255), width=6)
    img = Image.alpha_composite(img, crisp)

    img.alpha_composite(_circle_avatar(avatar_bytes, size, (username or "?")[0].upper()), (left, top))

    draw = ImageDraw.Draw(img)
    title, tsize = "WELCOME TO WORLD WAR APE", 70
    while tsize > 24 and draw.textlength(title, font=_font(tsize)) > W - 90:
        tsize -= 2
    _centered(draw, title, 292, _font(tsize), (242, 236, 220))
    _centered(draw, username[:28], 346, _font(40), (255, 170, 60), stroke=2)
    _centered(draw, f"Member #{member_number:,}", 396, _font(30), (205, 205, 195), stroke=2)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    buf.seek(0)
    return buf


async def send_welcome(member: discord.Member):
    guild = member.guild
    channel = find_channel(guild, WELCOME_CHANNEL)
    if channel is None:
        return
    try:
        avatar = await member.display_avatar.replace(size=256, format="png").read()
    except Exception:
        avatar = None
    png = await asyncio.to_thread(make_welcome_card, avatar, member.name, guild.member_count)

    verify = find_channel(guild, VERIFY_CHANNEL)
    rules = find_channel(guild, RULES_CHANNEL)
    await channel.send(file=discord.File(png, filename="welcome.png"))
    await channel.send(
        f"Welcome {member.mention}! 🐒 Head to {verify.mention if verify else 'the verify channel'} "
        f"to verify and read {rules.mention if rules else 'the rules'}.",
        allowed_mentions=discord.AllowedMentions(users=[member]))
