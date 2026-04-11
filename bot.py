import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os

TOKEN = os.getenv("TOKEN")
SERVER_ID = int(os.getenv("SERVER_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- DATABASE ---------------- #

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    discord_id TEXT PRIMARY KEY,
    total_earnings REAL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    description TEXT,
    reward_per_clip REAL,
    active INTEGER DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS campaign_members (
    discord_id TEXT,
    campaign_id INTEGER,
    PRIMARY KEY (discord_id, campaign_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS submissions (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT,
    campaign_id INTEGER,
    link TEXT,
    status TEXT DEFAULT 'pending'
)
""")

# ---------------- PAYMENT TABLES ---------------- #

cursor.execute("""
CREATE TABLE IF NOT EXISTS payment_methods (
    discord_id TEXT PRIMARY KEY,
    method TEXT,
    details TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payout_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT,
    amount REAL,
    status TEXT DEFAULT 'pending'
)
""")

class SubmitClipModal(discord.ui.Modal, title="Submit Clip"):

    link = discord.ui.TextInput(label="Paste Video Link", required=True)
    note = discord.ui.TextInput(label="Optional Note", style=discord.TextStyle.paragraph, required=False)

    async def on_submit(self, interaction: discord.Interaction):

        review_channel = discord.utils.get(interaction.guild.text_channels, name="clip-submissions")

        if review_channel:
            await review_channel.send(
                f"🎬 **New Submission**\n"
                f"User: {interaction.user.mention}\n"
                f"Link: {self.link}\n"
                f"Note: {self.note or 'None'}"
            )

        await interaction.response.send_message("✅ Submission sent!", ephemeral=True)

class PaymentModal(discord.ui.Modal, title="Payment Method"):

    method = discord.ui.TextInput(label="Method (PayPal, Cash App, Venmo, Crypto)", required=True)
    details = discord.ui.TextInput(label="Enter your payment details", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):

        cursor.execute(
            "INSERT OR REPLACE INTO payment_methods (discord_id, method, details) VALUES (?, ?, ?)",
            (str(interaction.user.id), self.method, self.details)
        )
        conn.commit()

        await interaction.response.send_message("✅ Payment method saved!", ephemeral=True)

class PayoutModal(discord.ui.Modal, title="Request Payout"):

    amount = discord.ui.TextInput(label="Enter payout amount", required=True)

    async def on_submit(self, interaction: discord.Interaction):

        cursor.execute(
            "INSERT INTO payout_requests (discord_id, amount) VALUES (?, ?)",
            (str(interaction.user.id), float(self.amount))
        )
        conn.commit()

        payout_channel = discord.utils.get(interaction.guild.text_channels, name="payouts")

        if payout_channel:
            await payout_channel.send(
                f"💰 **New Payout Request**\n"
                f"User: {interaction.user.mention}\n"
                f"Amount: ${self.amount}"
            )

        await interaction.response.send_message("✅ Payout request submitted!", ephemeral=True)

class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📊 Dashboard", style=discord.ButtonStyle.primary)
    async def dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):

        cursor.execute(
            "SELECT COUNT(*) FROM submissions WHERE discord_id=?",
            (str(interaction.user.id),)
        )
        total_submissions = cursor.fetchone()[0]

        cursor.execute(
            "SELECT total_earnings FROM users WHERE discord_id=?",
            (str(interaction.user.id),)
        )
        result = cursor.fetchone()
        total_earnings = result[0] if result else 0

        embed = discord.Embed(
            title="📊 Your Clip.Hub Dashboard",
            color=discord.Color.blurple()
        )

        embed.add_field(name="🎬 Total Submissions", value=str(total_submissions), inline=False)
        embed.add_field(name="💰 Total Earnings", value=f"${total_earnings}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📤 Submit Content", style=discord.ButtonStyle.primary)
    async def submit_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SubmitClipModal())

    @discord.ui.button(label="💳 Payment Methods", style=discord.ButtonStyle.primary)
    async def payment_methods(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PaymentModal())

    @discord.ui.button(label="💰 Request Payout", style=discord.ButtonStyle.primary)
    async def request_payout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PayoutModal())

conn.commit()

# ---------------- DASHBOARD VIEW ---------------- #

class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📊 Dashboard", style=discord.ButtonStyle.primary)
    async def dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "📊 Your dashboard stats will appear here soon.",
            ephemeral=True
        )

    @discord.ui.button(label="📤 Submit Content", style=discord.ButtonStyle.secondary)
    async def submit_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "📤 Use /submit to send your clips to active campaigns.",
            ephemeral=True
        )

    @discord.ui.button(label="💳 Payment Methods", style=discord.ButtonStyle.secondary)
    async def payment_methods(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "💳 Payment method management coming soon.",
            ephemeral=True
        )

    @discord.ui.button(label="💰 Request Payout", style=discord.ButtonStyle.success)
    async def request_payout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "💰 Payout request system coming soon.",
            ephemeral=True
        )

# ---------------- SUBMISSION REVIEW BUTTONS ---------------- #

class SubmissionReviewView(discord.ui.View):
    def __init__(self, submission_id):
        super().__init__(timeout=None)
        self.submission_id = submission_id

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        cursor.execute(
            "UPDATE submissions SET status='approved' WHERE submission_id=?",
            (self.submission_id,)
        )
        conn.commit()

        await interaction.message.edit(content="✅ Submission Approved", view=None)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        cursor.execute(
            "UPDATE submissions SET status='rejected' WHERE submission_id=?",
            (self.submission_id,)
        )
        conn.commit()

        await interaction.message.edit(content="❌ Submission Rejected", view=None)

    @discord.ui.button(label="💬 Request Fix", style=discord.ButtonStyle.secondary)
    async def request_fix(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        cursor.execute(
            "UPDATE submissions SET status='fix_requested' WHERE submission_id=?",
            (self.submission_id,)
        )
        conn.commit()

        await interaction.message.edit(content="💬 Fix Requested", view=None)

# ---------------- READY ---------------- #

@bot.event
async def on_ready():
    guild = discord.Object(1349487425814266006)
    await bot.tree.sync(guild=guild)
    bot.add_view(DashboardView())
    print(f"✅ Logged in as {bot.user}")

# ---------------- CREATE CAMPAIGN ---------------- #

@bot.tree.command(
    name="create-campaign",
    description="Create a campaign (Admin only)",
    guild=discord.Object(id=SERVER_ID)
)
@app_commands.describe(name="Campaign name", description="Description", reward="Reward per clip")
async def create_campaign(interaction: discord.Interaction, name: str, description: str, reward: float):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    try:
        cursor.execute(
            "INSERT INTO campaigns (name, description, reward_per_clip) VALUES (?, ?, ?)",
            (name, description, reward)
        )
        conn.commit()
        await interaction.response.send_message(f"✅ Campaign **{name}** created!")
    except sqlite3.IntegrityError:
        await interaction.response.send_message("❌ Campaign already exists.", ephemeral=True)

# ---------------- VIEW CAMPAIGNS ---------------- #

@bot.tree.command(
    name="campaigns",
    description="View active campaigns",
    guild=discord.Object(id=SERVER_ID)
)
async def campaigns(interaction: discord.Interaction):

    cursor.execute("SELECT name, description, reward_per_clip FROM campaigns WHERE active=1")
    results = cursor.fetchall()

    if not results:
        await interaction.response.send_message("No active campaigns.")
        return

    message = "**📢 Active Campaigns**\n\n"

    for campaign in results:
        message += (
            f"**{campaign[0]}**\n"
            f"{campaign[1]}\n"
            f"💰 Reward: {campaign[2]} per clip\n\n"
        )

    await interaction.response.send_message(message)

# ---------------- JOIN CAMPAIGN ---------------- #

@bot.tree.command(
    name="join",
    description="Join a campaign",
    guild=discord.Object(id=SERVER_ID)
)
@app_commands.describe(name="Campaign name")
async def join(interaction: discord.Interaction, name: str):

    cursor.execute("SELECT campaign_id FROM campaigns WHERE name=? AND active=1", (name,))
    result = cursor.fetchone()

    if not result:
        await interaction.response.send_message("❌ Campaign not found.", ephemeral=True)
        return

    campaign_id = result[0]

    try:
        cursor.execute(
            "INSERT INTO campaign_members (discord_id, campaign_id) VALUES (?, ?)",
            (str(interaction.user.id), campaign_id)
        )
        conn.commit()

        cursor.execute(
            "INSERT OR IGNORE INTO users (discord_id) VALUES (?)",
            (str(interaction.user.id),)
        )
        conn.commit()

        await interaction.response.send_message(f"✅ You joined **{name}**!")
    except sqlite3.IntegrityError:
        await interaction.response.send_message("❌ Already joined.", ephemeral=True)

# ---------------- SUBMIT ---------------- #

@bot.tree.command(
    name="submit",
    description="Submit a clip",
    guild=discord.Object(id=SERVER_ID)
)
@app_commands.describe(campaign="Campaign name", link="TikTok or YouTube link")
async def submit(interaction: discord.Interaction, campaign: str, link: str):

    cursor.execute("SELECT campaign_id FROM campaigns WHERE name=? AND active=1", (campaign,))
    result = cursor.fetchone()

    if not result:
        await interaction.response.send_message("❌ Campaign not found.", ephemeral=True)
        return

    campaign_id = result[0]

    cursor.execute(
        "INSERT INTO submissions (discord_id, campaign_id, link) VALUES (?, ?, ?)",
        (str(interaction.user.id), campaign_id, link)
    )
    conn.commit() 

    submission_id = cursor.lastrowid

    review_channel = discord.utils.get(interaction.guild.text_channels, name="clip-submissions")

    if review_channel:
    
        view = SubmissionReviewView(submission_id)

    await review_channel.send(
        f"🎬 **New Submission**\n"
        f"User: {interaction.user.mention}\n"
        f"Campaign: {campaign}\n"
        f"Link: {link}\n"
        f"Status: Pending",
        view=view
    )
        

    await interaction.response.send_message("✅ Submission sent for review!", ephemeral=True)

# ---------------- PROFILE ---------------- #

@bot.tree.command(
    name="profile",
    description="View your profile",
    guild=discord.Object(id=SERVER_ID)
)
async def profile(interaction: discord.Interaction):

    try:
        # Ensure user exists in users table
        cursor.execute(
            "INSERT OR IGNORE INTO users (discord_id) VALUES (?)",
            (str(interaction.user.id),)
        )
        conn.commit()

        # Count submissions
        cursor.execute(
            "SELECT COUNT(*) FROM submissions WHERE discord_id=?",
            (str(interaction.user.id),)
        )
        total_submissions = cursor.fetchone()[0]

        # Get earnings
        cursor.execute(
            "SELECT total_earnings FROM users WHERE discord_id=?",
            (str(interaction.user.id),)
        )
        result = cursor.fetchone()

        total_earnings = result[0] if result else 0

        await interaction.response.send_message(
            f"👤 **{interaction.user.name}'s Profile**\n\n"
            f"🎬 Total Submissions: {total_submissions}\n"
            f"💰 Total Earnings: {total_earnings}"
        )

    except Exception as e:
        print("Profile error:", e)
        await interaction.response.send_message(
            "❌ Something went wrong.",
            ephemeral=True
        )

# ---------------- INSPIRATION COMMAND ---------------- #

@bot.tree.command(
    name="inspiration",
    description="Post an inspiration earnings message (Staff only)",
    guild=discord.Object(id=SERVER_ID)
)
@app_commands.describe(
    user="User who earned",
    total="Total earned amount",
    campaign="Campaign name",
    link="Paste the video link"
)
async def inspiration(
    interaction: discord.Interaction,
    user: discord.Member,
    total: float,
    campaign: str,
    link: str
):

    # Allow Admins OR Mods
    perms = interaction.user.guild_permissions

    if not (perms.administrator or perms.manage_messages or perms.manage_roles):
        await interaction.response.send_message(
            "❌ Staff only.",
            ephemeral=True
        )
        return

    # Find the inspiration channel
    channel = discord.utils.get(
        interaction.guild.text_channels,
        name="📊│inspiration"
    )

    if not channel:
        await interaction.response.send_message(
            "❌ Channel '📊│inspiration' not found.",
            ephemeral=True
        )
        return

    # Format message with Markdown link
    message = (
        f"🎉 **{user.mention}** just earned **${total}** "
        f"from this clip in the **{campaign}** campaign! 🤑\n\n"
        f"[Watch Clip]({link})"
    )

    await channel.send(message)

    await interaction.response.send_message(
        "✅ Inspiration posted!",
        ephemeral=True
    )

# ---------------- CREATE DASHBOARD MESSAGE ---------------- #

@bot.tree.command(
    name="create-dashboard",
    description="Create the Clip.Hub dashboard (Admin only)",
    guild=discord.Object(id=SERVER_ID)
)
async def create_dashboard(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Admin only.",
            ephemeral=True
        )
        return

    view = DashboardView()

   embed = discord.Embed(
    title="✨ Welcome to your Clip.Hub Dashboard",
    description=(
        "Use the options below to manage everything:\n\n"
        "📊 **Dashboard** – Track your posts, views, and earnings\n"
        "📤 **Submit Content** – Send your clips to active campaigns\n"
        "💳 **Payment Methods** – Choose how you want to get paid\n"
        "💰 **Request Payout** – Request a payout from your balance\n"
        "🎬 **Submit Clip** – Get feedback on campaign videos"
    ),
    color=discord.Color.blurple()
)

await interaction.channel.send(embed=embed, view=DashboardView())
    
    await interaction.response.send_message(
        "✅ Dashboard created!",
        ephemeral=True
    )

bot.run(TOKEN)