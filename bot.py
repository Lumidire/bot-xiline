import os
import discord
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"¡Xiline está conectado como {bot.user}!")

class TournamentView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Inscribirse 📝", style=discord.ButtonStyle.green, custom_id="btn_inscribir")
    async def inscribir(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("¡Te has inscrito correctamente al torneo!", ephemeral=True)

    @discord.ui.button(label="Desinscribirse ❌", style=discord.ButtonStyle.red, custom_id="btn_desinscribir")
    async def desinscribir(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Te has desinscrito del torneo.", ephemeral=True)

@bot.command()
@commands.has_permissions(administrator=True)
async def panel(ctx):
    embed = discord.Embed(
        title="🏆 Inscripciones Abiertas - Los Muertos Fc",
        description="Haz clic en los botones de abajo para asegurar tu cupo o retirarte del torneo diario.",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Xiline Bot • Sistema de Torneos")
    await ctx.send(embed=embed, view=TournamentView())

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)