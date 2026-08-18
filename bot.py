import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Gekoppelde tekstkanalen
APPLICATION_CHANNEL_ID = 1539069061902766110  # Waar spelers !setup_app typen
QUEUE_CHANNEL_ID = 1539069138633236550        # Waar de match-kaarten komen te staan

# ----------------------------------------------------
# 1. STEP 2 POP-UP: THE CHALLENGER FIELDS
# ----------------------------------------------------
class ChallengeModal(discord.ui.Modal):
    def __init__(self, mode: str, original_leader: str, host_id: int, server_choice: str, message: discord.Message):
        # We maken de titel super kort om laadtijd te besparen
        super().__init__(title=f"Challenge {mode}")
        self.mode = mode
        self.original_leader = original_leader
        self.host_id = host_id
        self.server_choice = server_choice
        self.message = message  

        label_text = "What is your Discord Display Name?" if mode == "1v1" else "Group members Discord Display Names?"
        placeholder_text = "e.g. imitorr" if mode == "1v1" else "e.g. imitorr, wastedchack"

        self.opponents = discord.ui.TextInput(
            label=label_text,
            placeholder=placeholder_text,
            style=discord.TextStyle.short if mode == "1v1" else discord.TextStyle.long,
            required=True
        )
        self.add_item(self.opponents)

    async def on_submit(self, interaction: discord.Interaction):
        # Direct uitstellen om ELKE vorm van lag of timeout te voorkomen
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        challenger = interaction.user
        host_member = guild.get_member(self.host_id)

        # Lock original card en update visual layout
        disabled_embed = discord.Embed(
            title=f"🔒 {self.mode} Match Closed / Filled",
            description=(
                f"**Host / Group Members:**\n{self.original_leader}\n\n"
                f"**Server:** {self.server_choice}\n\n"
                f"**Challenger / Opponents:**\n{self.opponents.value}"
            ),
            color=discord.Color.greyple()
        )
        disabled_embed.set_footer(text="This match is locked. Private match room created.")
        
        disabled_view = discord.ui.View()
        disabled_btn = discord.ui.Button(label="Match Filled", style=discord.ButtonStyle.grey, disabled=True)
        disabled_view.add_item(disabled_btn)
        
        await self.message.edit(embed=disabled_embed, view=disabled_view)

        # Create Private Match Text Channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
            challenger: discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True),
        }
        
        if host_member:
            overwrites[host_member] = discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True)

        channel_name = f"💥-{self.mode}-{interaction.user.name}"
        match_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)

        private_msg = (
            f"⚔️ **Match Room Created!** ⚔️\n"
            f"**Mode:** {self.mode}\n"
            f"**Server Location:** {self.server_choice}\n\n"
            f"**Team 1 (Host):** {self.original_leader} ({f'<@{self.host_id}>' if host_member else ''})\n"
            f"**Team 2 (Challenger):** {self.opponents.value} ({challenger.mention})\n\n"
            f"Coordinate your lobby setup details here safely. Nobody else can view this room."
        )
        await match_channel.send(private_msg)

        match_alert = (
            f"⚔️ **Match Confirmed!** ⚔️\n"
            f"**Mode:** {self.mode}\n\n"
            f"**Team 1 (Host):** {self.original_leader}\n"
            f"**Team 2 (Challenger):** {self.opponents.value} (Accepted by {challenger.mention})\n\n"
            f"Private match room created: {match_channel.mention}"
        )
        await interaction.channel.send(match_alert)
        await interaction.followup.send(f"Challenge confirmed! Room created: {match_channel.mention}", ephemeral=True)


# ----------------------------------------------------
# 2. MATCH DISPATCH PANEL BUTTON
# ----------------------------------------------------
class ChallengeView(discord.ui.View):
    def __init__(self, mode: str, original_leader: str, host_id: int, server_choice: str):
        super().__init__(timeout=None)
        self.mode = mode
        self.original_leader = original_leader
        self.host_id = host_id
        self.server_choice = server_choice

    @discord.ui.button(label="Challenge", style=discord.ButtonStyle.danger, custom_id="challenge_btn")
    async def challenge_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.host_id:
            await interaction.response.send_message("You cannot challenge your own match card!", ephemeral=True)
            return
            
        await interaction.response.send_modal(ChallengeModal(
            mode=self.mode, 
            original_leader=self.original_leader, 
            host_id=self.host_id, 
            server_choice=self.server_choice,
            message=interaction.message
        ))


# ----------------------------------------------------
# 3. CARD SENDER LOGIC
# ----------------------------------------------------
async def send_to_queue_channel(bot_instance, mode: str, leader_name: str, server_choice: str, host_id: int):
    channel = bot_instance.get_channel(QUEUE_CHANNEL_ID)
    if not channel:
        print("Error: Could not locate queue channel.")
        return

    embed = discord.Embed(
        title=f"⚔️ New {mode} Match Hosted!",
        color=discord.Color.red()
    )
    embed.add_field(name="Host / Group Members (Discord Display Names)", value=leader_name, inline=False)
    embed.add_field(name="Server Requested", value=server_choice, inline=False)
    embed.set_footer(text="Click the button below to submit your team and fight them!")

    await channel.send(embed=embed, view=ChallengeView(mode=mode, original_leader=leader_name, host_id=host_id, server_choice=server_choice))


# ----------------------------------------------------
# 4. STEP 1 POP-UP: THE HOST FIELDS (VLIEDERLICHT GEMAAKT)
# ----------------------------------------------------
class HostModal(discord.ui.Modal):
    def __init__(self, mode: str):
        # We halen de logica uit de __init__ om de pop-up onmiddellijk te laten openen
        super().__init__(title=f"Host Menu ({mode})")
        self.mode = mode

        label_text = "What is your Discord Display Name?" if mode == "1v1" else "Group members Discord Display Names?"
        placeholder_text = "e.g. imitorr" if mode == "1v1" else "e.g. imitorr, wastedchack"

        self.ign = discord.ui.TextInput(
            label=label_text,
            placeholder=placeholder_text,
            style=discord.TextStyle.short if mode == "1v1" else discord.TextStyle.long,
            required=True
        )
        self.server_input = discord.ui.TextInput(
            label="What server do you want this to happen on?",
            placeholder="e.g. Eu.stray.gg",
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.ign)
        self.add_item(self.server_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Direct uitstellen om de timeout voor te zijn
        await interaction.response.defer(ephemeral=True)
        await send_to_queue_channel(interaction.client, self.mode, self.ign.value, self.server_input.value, interaction.user.id)
        await interaction.followup.send("Lobby posted to the queue channel!", ephemeral=True)


# ----------------------------------------------------
# 5. INITIAL DISPLAY PANEL VIEW
# ----------------------------------------------------
class ApplicationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="1v1", style=discord.ButtonStyle.green, custom_id="app_1v1")
    async def button_1v1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HostModal(mode="1v1"))

    @discord.ui.button(label="2v2", style=discord.ButtonStyle.green, custom_id="app_2v2")
    async def button_2v2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HostModal(mode="2v2"))

    @discord.ui.button(label="3v3", style=discord.ButtonStyle.green, custom_id="app_3v3")
    async def button_3v3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HostModal(mode="3v3"))


# ----------------------------------------------------
# 6. ENGINE EXECUTION LOGIC
# ----------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} - Bot is online!")

@bot.command()
async def setup_app(ctx):
    if ctx.channel.id != APPLICATION_CHANNEL_ID:
        await ctx.send("This command can only be used in the application channel!", delete_after=5)
        return

    embed = discord.Embed(
        title="Welcome to Matchmaking System!",
        description="Select your match setup below to post your open game ticket to the queue channel.",
        color=discord.Color.dark_theme()
    )
    embed.set_footer(text="Match System Bot")
    
    await ctx.send(embed=embed, view=ApplicationView())

# Haalt de token nu volledig veilig op uit Render
bot.run(os.environ.get('DISCORD_TOKEN'))
