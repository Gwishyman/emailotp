import discord
from discord.ext import commands
import smtplib
import secrets
import time
import csv
import os
from email.message import EmailMessage

# =========================
# CONFIG
# =========================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

OTP_EXPIRY_SECONDS = 300  # 5 minutes
CSV_FILE = "stored.csv"

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# STORAGE
# =========================
otp_store = {}

# =========================
# CSV FUNCTIONS
# =========================
def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["email", "username"])


def save_verified_user(email, username):
    init_csv()

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2 and row[1] == username:
                return  # already stored

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([email, username])

# =========================
# OTP FUNCTIONS
# =========================
def generate_otp(length=6):
    digits = "0123456789"
    return ''.join(secrets.choice(digits) for _ in range(length))


def send_otp_email(receiver, otp):
    msg = EmailMessage()
    msg["Subject"] = "Your Discord OTP Code"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = receiver
    msg.set_content(
        f"Your OTP code is: {otp}\n\n"
        f"This code expires in 5 minutes."
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

# =========================
# BOT EVENTS
# =========================
@bot.event
async def on_ready():
    init_csv()
    print(f"Logged in as {bot.user}")

# =========================
# COMMANDS
# =========================
@bot.command()
async def otp(ctx):
    guild_name = ctx.guild.name if ctx.guild else "ERROR"
    """Start OTP verification"""

    try:
        await ctx.author.send("Please reply with your email address.")
        await ctx.reply("Check your DMs to continue.", delete_after=5)
    except discord.Forbidden:
        await ctx.reply("I can't DM you. Enable DMs and try again.")
        return

    def dm_check(m):
        return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)

    # Get email
    try:
        email_msg = await bot.wait_for("message", timeout=60, check=dm_check)
    except:
        await ctx.author.send("Timed out.")
        return

    email = email_msg.content.strip()

    otp = generate_otp()
    otp_store[ctx.author.id] = {
        "email": email,
        "otp": otp,
        "expires": time.time() + OTP_EXPIRY_SECONDS
    }

    try:
        send_otp_email(email, otp)
        await ctx.author.send("OTP sent. Please reply with the OTP.")
    except:
        await ctx.author.send("Failed to send email.")
        del otp_store[ctx.author.id]
        return

    # Get OTP
    try:
        otp_msg = await bot.wait_for("message", timeout=OTP_EXPIRY_SECONDS, check=dm_check)
    except:
        await ctx.author.send("OTP expired.")
        del otp_store[ctx.author.id]
        return

    record = otp_store.get(ctx.author.id)

    if not record:
        await ctx.author.send("No OTP request found.")
        return

    if time.time() > record["expires"]:
        del otp_store[ctx.author.id]
        await ctx.author.send("OTP expired.")
        return

    if otp_msg.content.strip() != record["otp"]:
        await ctx.author.send("Incorrect OTP.")
        return

    # VERIFIED SUCCESSFULLY
    username = f"@{ctx.author.name}"
    save_verified_user(record["email"], username)
    del otp_store[ctx.author.id]

    await ctx.author.send(f"OTP verified successfully! You can now access the server **{guild_name}**.")

# =========================
# RUN BOT
# =========================
bot.run(DISCORD_TOKEN)
