from flask import Flask
from threading import Thread
import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

# --- SERVIDOR WEB PARA EVITAR QUE RENDER APAGUE EL BOT ---
app = Flask('')

@app.route('/')
def home():
    return "¡El bot de Los Muertos FC está vivo y activo!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# IDs configurados de tu servidor
ROL_LIGA_ID = 1566864268979085432
ROL_VETADO_ID = 1566865203058970684
CANAL_LOGS_ID = 1565940015517794336

# Almacenamiento temporal en memoria
historial_warns = {}
historial_sanciones = {}

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

class BotXiline(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)

    async def setup_hook(self):
        await self.tree.sync()
        print("¡Comandos de barra sincronizados correctamente!")

bot = BotXiline()

# --- SISTEMA DE LOGS LIMPIO (LOGS | TÍTULO) ---
async def enviar_log_embed(guild, titulo, descripcion, color, campos=None):
    canal = guild.get_channel(CANAL_LOGS_ID)
    if not canal:
        try:
            canal = await guild.fetch_channel(CANAL_LOGS_ID)
        except Exception as e:
            print(f"No se pudo obtener el canal de logs: {e}")
            return

    embed = discord.Embed(
        title=f"📋 LOGS | {titulo}",
        description=descripcion,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    if campos:
        for nombre, valor, en_linea in campos:
            embed.add_field(name=nombre, value=valor, inline=en_linea)

    embed.set_footer(text=f"Servidor: {guild.name}")

    try:
        await canal.send(embed=embed)
    except Exception as e:
        print(f"Error al enviar log en embed: {e}")

@bot.event
async def on_ready():
    print(f'¡Conectado exitosamente como {bot.user}!')

# --- MANEJADOR DE ERRORES ÚNICO Y ANTIDUPLICADOS ---
@bot.event
async def on_command_error(ctx, error):
    if hasattr(ctx, 'handled') and ctx.handled:
        return
    ctx.handled = True

    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title="❌ Comando Inválido",
            description="El comando que intentaste usar no existe o está mal escrito. Usa `!ayuda` para ver la lista de comandos disponibles.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        embed = discord.Embed(
            title="⚠️ Faltan Datos o Argumentos",
            description="Te faltó incluir información obligatoria o algún usuario/dato es incorrecto para este comando.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed, delete_after=10)
    else:
        print(f"Error ignorado: {error}")

# ==========================================
# 1. UTILIDAD Y COMUNIDAD
# ==========================================

@bot.hybrid_command(name="ayuda", description="Muestra la lista de comandos disponibles.")
async def ayuda_command(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="🤖 Menú de Ayuda - Bot Xiline (Los Muertos FC)",
        description="Aquí tienes la lista oficial de comandos organizada para la administración de Los Muertos FC.",
        color=discord.Color.blue()
    )
    embed.add_field(name="📢 Comunidad", value="`!anuncio [mensaje]` / `/anuncio` - Envía un anuncio oficial.", inline=False)
    embed.add_field(name="⚖️ Moderación y Sanciones", value="`!warn` / `/warn` - Registra advertencias.\n`!sancion` / `/sancion` - Sanción inteligente por niveles.\n`!ver-sanciones` - Revisa el historial de un usuario.", inline=False)
    embed.add_field(name="🚫 Sistema de Vetos", value="`!vetar` / `/vetar` - Prohíbe la inscripción a torneos.\n`!desvetar` / `/desvetar` - Remueve el veto.", inline=False)
    embed.add_field(name="🏆 Torneo Los Muertos FC", value="`/crear-inscripcion [cupos]` - Crea el panel de inscripción con botones (4, 8, 16, 32).", inline=False)
    
    if ctx.interaction:
        await ctx.channel.send(embed=embed)
        try:
            await ctx.interaction.delete_original_response()
        except:
            pass
    else:
        await ctx.send(embed=embed)

@bot.hybrid_command(name="anuncio", description="Envía un anuncio oficial en embed limpio con mención global real.")
@app_commands.describe(
    mensaje="El contenido del anuncio oficial",
    imagen="URL opcional de una imagen o banner para el embed"
)
async def anuncio(ctx, mensaje: str, imagen: str = None):
    if ctx.interaction:
        await ctx.interaction.response.defer(ephemeral=True)

    mencion_global = ""
    if "@everyone" in mensaje:
        mencion_global = "@everyone"
    elif "@here" in mensaje:
        mencion_global = "@here"

    embed = discord.Embed(
        title="📢 ¡Aviso Oficial de Los Muertos FC!",
        description=mensaje,
        color=discord.Color.gold()
    )
    if imagen:
        embed.set_image(url=imagen)

    allowed_menciones = discord.AllowedMentions(everyone=True, roles=True, users=True)

    if not ctx.interaction:
        try:
            await ctx.message.delete()
        except:
            pass

    if mencion_global:
        await ctx.send(content=mencion_global, embed=embed, allowed_mentions=allowed_menciones)
    else:
        await ctx.send(embed=embed)

    if ctx.interaction:
        try:
            await ctx.interaction.delete_original_response()
        except:
            pass

    await enviar_log_embed(
        ctx.guild,
        "Anuncio Oficial Enviado",
        "Se ha emitido un comunicado oficial en Los Muertos FC.",
        discord.Color.gold(),
        [
            ("Moderador", ctx.author.mention, True),
            ("Canal", ctx.channel.mention, True)
        ]
    )


# ==========================================
# 2. SISTEMA DE SANCIONES Y WARNS
# ==========================================

@bot.hybrid_command(name="sancion", description="Aplica el sistema inteligente de sanciones.")
@app_commands.describe(usuario="El miembro a sancionar", horas_opcional="Horas de timeout opcionales (por defecto 2h)")
async def sancion(ctx, usuario: discord.Member, horas_opcional: int = 2):
    if ctx.interaction:
        await ctx.interaction.response.defer(ephemeral=True)

    user_id = usuario.id
    if user_id not in historial_sanciones:
        historial_sanciones[user_id] = 0
    
    historial_sanciones[user_id] += 1
    nivel = historial_sanciones[user_id]
    guild = ctx.guild
    rol_liga = guild.get_role(ROL_LIGA_ID)

    if nivel == 1:
        embed = discord.Embed(title="📌 1ra Sanción Registrada", description=f"A {usuario.mention} se le ha registrado su primera sanción formal.", color=discord.Color.yellow())
        if ctx.interaction:
            await ctx.channel.send(embed=embed)
            try:
                await ctx.interaction.followup.send("✅ Sanción nivel 1 aplicada.", ephemeral=True)
            except:
                pass
        else:
            await ctx.send(embed=embed)
            
        await enviar_log_embed(
            guild, "1ra Sanción Registrada", f"Se registró la primera sanción a {usuario.mention}.", discord.Color.yellow(),
            [("Moderador", ctx.author.mention, True), ("Usuario", usuario.mention, True), ("Nivel", "1", True)]
        )
        
    elif nivel == 2:
        delta_tiempo = datetime.now(timezone.utc) + discord.timedelta(hours=horas_opcional)
        try:
            await usuario.timeout(delta_tiempo, reason=f"2da Sanción ({horas_opcional} horas)")
            msg = f"⏳ **{usuario.mention}** recibió su **2da Sanción**: Timeout de **{horas_opcional} horas**."
            
            if ctx.interaction:
                await ctx.channel.send(msg)
                try:
                    await ctx.interaction.followup.send(f"✅ Timeout de {horas_opcional}h aplicado con éxito.", ephemeral=True)
                except:
                    pass
            else:
                await ctx.send(msg)
                
            await enviar_log_embed(
                guild, "2da Sanción Aplicada (Timeout)", f"Se aplicó un timeout de {horas_opcional} horas a {usuario.mention}.", discord.Color.orange(),
                [("Moderador", ctx.author.mention, True), ("Usuario", usuario.mention, True), ("Duración", f"{horas_opcional} horas", True)]
            )
        except Exception as e:
            print(f"Error al aplicar timeout en nivel 2: {e}")
            if ctx.interaction:
                try:
                    await ctx.interaction.followup.send("❌ Error: No se pudo aplicar el timeout (revisa jerarquía de roles del bot).", ephemeral=True)
                except:
                    pass

    elif nivel >= 3:
        es_miembro_liga = rol_liga in usuario.roles if rol_liga else False
        delta_tiempo = datetime.now(timezone.utc) + discord.timedelta(hours=horas_opcional)
        if es_miembro_liga and rol_liga:
            try:
                await usuario.remove_roles(rol_liga, reason="3ra Sanción - Retiro de rol de liga")
                await usuario.timeout(delta_tiempo, reason="3ra Sanción miembro de liga")
                msg = f"🛑 **{usuario.mention}** (Miembro de Los Muertos FC) acumuló su **3ra Sanción**: Se le retiró el rol de la liga y recibió timeout de {horas_opcional}h."
                
                if ctx.interaction:
                    await ctx.channel.send(msg)
                    try:
                        await ctx.interaction.followup.send("✅ 3ra sanción procesada (Rol retirado + Timeout).", ephemeral=True)
                    except:
                        pass
                else:
                    await ctx.send(msg)
                    
                await enviar_log_embed(
                    guild, "3ra Sanción - Miembro de Liga", f"Se retiró el rol oficial de la liga a {usuario.mention} y se aplicó timeout.", discord.Color.red(),
                    [("Moderador", ctx.author.mention, True), ("Usuario", usuario.mention, True), ("Acción", "Retiro de Rol de Liga + Timeout", False)]
                )
            except Exception as e:
                print(f"Error en nivel 3 (liga): {e}")
        else:
            try:
                await usuario.kick(reason="3ra Sanción - Comunidad general")
                msg = f"👢 **{usuario.mention}** (Comunidad general) acumuló su **3ra Sanción** y fue expulsado (*kick*)."
                
                if ctx.interaction:
                    await ctx.channel.send(msg)
                    try:
                        await ctx.interaction.followup.send("✅ Usuario expulsado por acumular 3 sanciones.", ephemeral=True)
                    except:
                        pass
                else:
                    await ctx.send(msg)
                    
                await enviar_log_embed(
                    guild, "3ra Sanción - Miembro General (Kick)", f"El usuario {usuario.mention} fue expulsado del servidor por acumular 3 sanciones.", discord.Color.red(),
                    [("Moderador", ctx.author.mention, True), ("Usuario", usuario.mention, True), ("Acción", "Expulsión (Kick)", False)]
                )
            except Exception as e:
                print(f"Error en nivel 3 (kick): {e}")
                
# ==========================================
# 3. SISTEMA DE VETOS
# ==========================================

@bot.hybrid_command(name="vetar", description="Vetar a un usuario de los torneos de la liga.")
async def vetar(ctx, usuario: discord.Member, *, razon: str = "Infracción en torneos"):
    if ctx.interaction:
        await ctx.interaction.response.defer(ephemeral=True)

    guild = ctx.guild
    rol_vetado = guild.get_role(ROL_VETADO_ID)
    if not rol_vetado:
        msg = "El rol de vetado no existe en el servidor."
        if ctx.interaction:
            await ctx.channel.send(msg)
            try:
                await ctx.interaction.delete_original_response()
            except:
                pass
        else:
            await ctx.send(msg)
        return
    try:
        await usuario.add_roles(rol_vetado, reason=razon)
        msg = f"🚫 **{usuario.mention}** ha sido **vetado** de los torneos de Los Muertos FC. Razón: {razon}"
        if ctx.interaction:
            await ctx.channel.send(msg)
            try:
                await ctx.interaction.delete_original_response()
            except:
                pass
        else:
            await ctx.send(msg)
        await enviar_log_embed(
            guild, "Usuario Vetado de Torneos", f"Se le ha impuesto el rol de vetado a {usuario.mention}.", discord.Color.dark_red(),
            [("Moderador", ctx.author.mention, True), ("Usuario", usuario.mention, True), ("Razón", razon, False)]
        )
    except Exception as e:
        print(f"Error: {e}")

@bot.hybrid_command(name="desvetar", description="Remover el veto a un usuario.")
async def desvetar(ctx, usuario: discord.Member):
    if ctx.interaction:
        await ctx.interaction.response.defer(ephemeral=True)

    guild = ctx.guild
    rol_vetado = guild.get_role(ROL_VETADO_ID)
    if not rol_vetado:
        msg = "El rol de vetado no existe en el servidor."
        if ctx.interaction:
            await ctx.channel.send(msg)
            try:
                await ctx.interaction.delete_original_response()
            except:
                pass
        else:
            await ctx.send(msg)
        return
    try:
        await usuario.remove_roles(rol_vetado, reason="Remoción de veto")
        msg = f"✅ **{usuario.mention}** ya no está vetado en Los Muertos FC."
        if ctx.interaction:
            await ctx.channel.send(msg)
            try:
                await ctx.interaction.delete_original_response()
            except:
                pass
        else:
            await ctx.send(msg)
        await enviar_log_embed(
            guild, "Veto Removido", f"Se le ha retirado el veto a {usuario.mention}.", discord.Color.green(),
            [("Moderador", ctx.author.mention, True), ("Usuario", usuario.mention, True)]
        )
    except Exception as e:
        print(f"Error: {e}")


# ==========================================
# 4. TORNEO DE LIGAS (INSCRIPCIONES)
# ==========================================

class VistaInscripcionTorneo(discord.ui.View):
    def __init__(self, cupos_maximos: int, guild: discord.Guild):
        super().__init__(timeout=None)
        self.cupos_maximos = cupos_maximos
        self.guild = guild
        self.inscritos = []
        self.suplentes = []

    def actualizar_embed(self):
        embed = discord.Embed(
            title="🏆 INSCRIPCIÓN ABIERTA - TORNEO LOS MUERTOS FC",
            description=(
                f"Haz clic en el botón verde para asegurar tu cupo.\n"
                f"• **Cupos Principales:** {len(self.inscritos)} / {self.cupos_maximos}\n"
                f"• **Fila de Suplentes:** {len(self.suplentes)}"
            ),
            color=discord.Color.green()
        )
        titulares_txt = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(self.inscritos)]) if self.inscritos else "Ninguno todavía."
        embed.add_field(name="🟢 Titulares Principales", value=titulares_txt, inline=False)
        if self.suplentes:
            suplentes_txt = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(self.suplentes)])
            embed.add_field(name="🟡 Fila / Suplentes", value=suplentes_txt, inline=False)
        embed.set_footer(text=f"Límite configurado: {self.cupos_maximos} participantes.")
        return embed

    @discord.ui.button(label="Inscribirse", style=discord.ButtonStyle.success, custom_id="btn_inscribir_torneo")
    async def inscribirse(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        rol_vetado = self.guild.get_role(ROL_VETADO_ID)

        if rol_vetado and rol_vetado in user.roles:
            await interaction.response.send_message("❌ Estás **vetado** y no puedes inscribirte en Los Muertos FC.", ephemeral=True)
            return

        if user in self.inscritos or user in self.suplentes:
            await interaction.response.send_message("⚠️ Ya estás registrado en este torneo.", ephemeral=True)
            return

        if len(self.inscritos) < self.cupos_maximos:
            self.inscritos.append(user)
            await interaction.response.send_message("✅ ¡Inscrito como **Titular** en Los Muertos FC!", ephemeral=True)
            await enviar_log_embed(
                self.guild, "Inscripción a Torneo (Titular)", f"{user.mention} se ha inscrito formalmente como **Titular**.", discord.Color.blue(),
                [("Participante", user.mention, True), ("Estado", "Titular Principal", True), ("Total Titulares", f"{len(self.inscritos)}/{self.cupos_maximos}", True)]
            )
        else:
            self.suplentes.append(user)
            await interaction.response.send_message("⚠️ Cupos llenos. Has entrado a la **Fila de Suplentes**.", ephemeral=True)
            await enviar_log_embed(
                self.guild, "Inscripción a Torneo (Suplente)", f"{user.mention} entró a la **Fila de Suplentes** por cupos llenos.", discord.Color.gold(),
                [("Participante", user.mention, True), ("Estado", "Fila de Espera", True), ("Total Suplentes", str(len(self.suplentes)), True)]
            )

        await interaction.message.edit(embed=self.actualizar_embed(), view=self)

    @discord.ui.button(label="Desinscribirse", style=discord.ButtonStyle.danger, custom_id="btn_desinscribir_torneo")
    async def desinscribirse(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user

        if user in self.inscritos:
            self.inscritos.remove(user)
            movido_texto = "Ninguno"
            if self.suplentes:
                nuevo_titular = self.suplentes.pop(0)
                self.inscritos.append(nuevo_titular)
                movido_texto = nuevo_titular.mention
                await enviar_log_embed(
                    self.guild, "Ascenso Automático desde Suplentes", f"{nuevo_titular.mention} ha subido automáticamente de suplente a **Titular**.", discord.Color.purple(),
                    [("Nuevo Titular", nuevo_titular.mention, False)]
                )
            
            await interaction.response.send_message("✅ Te has desinscrito correctamente.", ephemeral=True)
            await enviar_log_embed(
                self.guild, "Desinscripción de Torneo", f"{user.mention} se ha desinscrito del torneo.", discord.Color.dark_orange(),
                [("Participante", user.mention, True), ("Ascendido desde suplentes", movido_texto, False)]
            )
            await interaction.message.edit(embed=self.actualizar_embed(), view=self)

        elif user in self.suplentes:
            self.suplentes.remove(user)
            await interaction.response.send_message("✅ Has salido de los suplentes.", ephemeral=True)
            await enviar_log_embed(
                self.guild, "Salida de Fila de Suplentes", f"{user.mention} ha salido de la lista de suplentes.", discord.Color.dark_gray(),
                [("Participante", user.mention, True)]
            )
            await interaction.message.edit(embed=self.actualizar_embed(), view=self)
        else:
            await interaction.response.send_message("⚠️ No estabas inscrito.", ephemeral=True)

@bot.hybrid_command(name="crear-inscripcion", description="Crea el panel de inscripciones con botones.")
@app_commands.describe(cupos="Tamaño de los cupos principales")
@app_commands.choices(cupos=[
    app_commands.Choice(name="4 Jugadores", value=4),
    app_commands.Choice(name="8 Jugadores", value=8),
    app_commands.Choice(name="16 Jugadores", value=16),
    app_commands.Choice(name="32 Jugadores", value=32),
])
async def crear_inscripcion(ctx, cupos: int):
    if ctx.interaction:
        await ctx.interaction.response.defer(ephemeral=True)

    vista = VistaInscripcionTorneo(cupos_maximos=cupos, guild=ctx.guild)
    embed = vista.actualizar_embed()
    
    if ctx.interaction:
        await ctx.channel.send(embed=embed, view=vista)
        try:
            await ctx.interaction.delete_original_response()
        except:
            pass
    else:
        await ctx.send(embed=embed, view=vista)
    
    await enviar_log_embed(
        ctx.guild, "Panel de Torneo Creado", f"Se ha abierto un panel de inscripción para el torneo de Los Muertos FC.", discord.Color.teal(),
        [("Creador", ctx.author.mention, True), ("Cupos Principales", str(cupos), True)]
    )

TOKEN = os.getenv('DISCORD_TOKEN')

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
