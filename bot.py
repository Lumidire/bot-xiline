import os
import discord
from discord.ext import commands
from discord import app_commands

# IDs configurados de tu servidor
ROL_LIGA_ID = 1566864268979085432
ROL_VETADO_ID = 1566865203058970684
CANAL_LOGS_ID = 1565940015517794336

# Almacenamiento temporal en memoria para historiales y torneos activos
historial_warns = {}
historial_sanciones = {}
torneos_activos = {} # Almacena datos del embed de inscripción activo

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

class BotXiline(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # Sincronizar los slash commands con Discord
        await self.tree.sync()
        print("¡Comandos de barra (slash commands) sincronizados correctamente!")

bot = BotXiline()

async def enviar_log(guild, mensaje):
    canal = guild.get_channel(CANAL_LOGS_ID)
    if canal:
        try:
            await canal.send(f"📋 **[LOG]** {mensaje}")
        except Exception as e:
            print(f"Error al enviar log: {e}")

@bot.event
async def on_ready():
    print(f'¡Conectado exitosamente como {bot.user}!')

# ==========================================
# 1. UTILIDAD Y COMUNIDAD
# ==========================================

@bot.hybrid_command(name="ayuda", description="Muestra la lista de comandos disponibles.")
async def ayuda_command(ctx):
    embed = discord.Embed(
        title="🤖 Menú de Ayuda - Bot Xiline (Los Muertos FC)",
        description="Aquí tienes la lista de comandos disponibles para moderación, comunidad y torneos de FC Mobile.",
        color=discord.Color.blue()
    )
    embed.add_field(name="📢 Comunidad", value="`!anuncio [mensaje]` / `/anuncio` - Envía un anuncio con mención global.", inline=False)
    embed.add_field(name="⚖️ Moderación y Sanciones", value="`!warn` / `/warn` - Registra una advertencia.\n`!sancion` / `/sancion` - Aplica sanción inteligente (Timeout/Kick/Retiro de rol).\n`!ver-sanciones` - Revisa el historial.", inline=False)
    embed.add_field(name="🚫 Sistema de Vetos", value="`!vetar` / `/vetar` - Prohíbe a alguien inscribirse en los torneos.\n`!desvetar` / `/desvetar` - Remueve el veto.", inline=False)
    embed.add_field(name="🏆 Torneo FC Mobile", value="`/crear-inscripcion [cupos]` - Crea el panel de inscripción con botones (4, 8, 16, 32).", inline=False)
    await ctx.send(embed=embed, ephemeral=True)

@bot.hybrid_command(name="anuncio", description="Envía un anuncio oficial en embed con mención global.")
@app_commands.describe(mensaje="El contenido del anuncio oficial")
async def anuncio(ctx, *, mensaje: str):
    # Detectar si hay menciones en el texto para hacer el tag real fuera del embed
    mencion_global = ""
    if "@everyone" in mensaje:
        mencion_global = "@everyone"
    elif "@here" in mensaje:
        mencion_global = "@here"

    embed = discord.Embed(
        title="📢 ¡Aviso Oficial de la Comunidad!",
        description=mensaje,
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Anuncio enviado por {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    
    # Enviar el mensaje con el tag afuera para que suene la notificación
    if mencion_global:
        await ctx.send(content=mencion_global, embed=embed)
    else:
        await ctx.send(embed=embed)
    
    if ctx.interaction:
        await ctx.interaction.response.send_message("Anuncio enviado con éxito.", ephemeral=True)

    await enviar_log(ctx.guild, f"El moderador {ctx.author.mention} envió un anuncio oficial.")


# ==========================================
# 2. SISTEMA DE SANCIóNES Y WARNS
# ==========================================

@bot.hybrid_command(name="warn", description="Registra una advertencia formal a un usuario sin castigo directo.")
@app_commands.describe(usuario="El miembro a sancionar", razon="Motivo de la advertencia")
async def warn(ctx, usuario: discord.Member, *, razon: str):
    user_id = usuario.id
    if user_id not in historial_warns:
        historial_warns[user_id] = []
    
    historial_warns[user_id].append(razon)
    total_warns = len(historial_warns[user_id])

    embed = discord.Embed(title="⚠️ Advertencia Registrada", color=discord.Color.orange())
    embed.add_field(name="Usuario", value=usuario.mention, inline=True)
    embed.add_field(name="Total Warns", value=str(total_warns), inline=True)
    embed.add_field(name="Razón", value=razon, inline=False)
    
    await ctx.send(embed=embed)
    await enviar_log(ctx.guild, f"A {usuario.mention} se le registró un warn (Total: {total_warns}). Razón: {razon}")

    # Al tercer warn, aplicar mute progresivo automático
    if total_warns >= 3:
        horas_mute = 6 # Mínimo 6 horas por defecto al llegar al 3er warn
        # Aquí puedes escalar lógicamente si acumula más de 3
        delta_tiempo = discord.utils.utcnow() + discord.timedelta(hours=horas_mute)
        try:
            await usuario.timeout(delta_tiempo, reason="Acumulación de 3 advertencias (Warns)")
            await ctx.send(f"🚨 **{usuario.mention}** ha alcanzado los 3 warns y recibió un mute automático de **{horas_mute} horas**.")
            await enviar_log(ctx.guild, f"{usuario.mention} recibió mute automático de {horas_mute}h por acumulación de 3 warns.")
        except Exception as e:
            await ctx.send(f"No se pudo aplicar el timeout al usuario: {e}")

@bot.hybrid_command(name="sancion", description="Aplica el sistema inteligente de sanciones acumuladas.")
@app_commands.describe(usuario="El miembro a sancionar", horas_opcional="Horas de timeout opcionales (por defecto 2h)")
async def sancion(ctx, usuario: discord.Member, horas_opcional: int = 2):
    user_id = usuario.id
    if user_id not in historial_sanciones:
        historial_sanciones[user_id] = 0
    
    historial_sanciones[user_id] += 1
    nivel = historial_sanciones[user_id]
    guild = ctx.guild

    rol_liga = guild.get_role(ROL_LIGA_ID)

    if nivel == 1:
        embed = discord.Embed(title="📌 1ra Sanción Registrada", description=f"A {usuario.mention} se le ha registrado oficialmente su primera sanción en el historial.", color=discord.Color.yellow())
        await ctx.send(embed=embed)
        await enviar_log(guild, f"Se registró la 1ra sanción a {usuario.mention} por parte de {ctx.author.mention}.")

    elif nivel == 2:
        delta_tiempo = discord.utils.utcnow() + discord.timedelta(hours=horas_opcional)
        try:
            await usuario.timeout(delta_tiempo, reason=f"2da Sanción aplicada ({horas_opcional} horas)")
            await ctx.send(f"⏳ **{usuario.mention}** ha recibido su **2da Sanción**: Timeout automático de **{horas_opcional} horas**.")
            await enviar_log(guild, f"Se aplicó 2da Sanción a {usuario.mention}: Timeout de {horas_opcional}h.")
        except Exception as e:
            await ctx.send(f"No se pudo aplicar el timeout: {e}")

    elif nivel >= 3:
        es_miembro_liga = rol_liga in usuario.roles if rol_liga else False
        delta_tiempo = discord.utils.utcnow() + discord.timedelta(hours=horas_opcional)

        if es_miembro_liga and rol_liga:
            try:
                await usuario.remove_roles(rol_liga, reason="3ra Sanción - Retiro de rol de liga")
                await usuario.timeout(delta_tiempo, reason="3ra Sanción de miembro de liga")
                await ctx.send(f"🛑 **{usuario.mention}** (Miembro de la Liga) acumuló su **3ra Sanción**: Se le ha retirado el rol oficial de la liga y aplicado un timeout de {horas_opcional} horas.")
                await enviar_log(guild, f"3ra Sanción a miembro de liga {usuario.mention}: Rol de liga retirado y timeout de {horas_opcional}h.")
            except Exception as e:
                await ctx.send(f"Error al procesar la sanción de liga: {e}")
        else:
            try:
                await usuario.kick(reason="3ra Sanción - Usuario de la comunidad general")
                await ctx.send(f"👢 **{usuario.mention}** (Comunidad general) acumuló su **3ra Sanción** y ha sido expulsado (*kick*) del servidor.")
                await enviar_log(guild, f"3ra Sanción a miembro general {usuario.mention}: Expulsado del servidor.")
            except Exception as e:
                await ctx.send(f"No se pudo expulsar al usuario: {e}")

@bot.hybrid_command(name="ver-sanciones", description="Muestra el historial de advertencias y sanciones de un usuario.")
async def ver_sanciones(ctx, usuario: discord.Member):
    user_id = usuario.id
    warns = historial_warns.get(user_id, [])
    sanciones_nivel = historial_sanciones.get(user_id, 0)

    embed = discord.Embed(title=f"📋 Historial de Sanciones: {usuario.display_name}", color=discord.Color.purple())
    embed.add_field(name="Nivel de Sanción Oficial", value=f"Nivel {sanciones_nivel}", inline=False)
    embed.add_field(name="Total de Warns", value=str(len(warns)), inline=False)
    
    if warns:
        razones_texto = "\n".join([f"• {r}" for r in warns])
        embed.add_field(name="Detalle de Warns", value=razones_texto, inline=False)
    else:
        embed.add_field(name="Detalle de Warns", value="Sin advertencias registradas.", inline=False)

    await ctx.send(embed=embed, ephemeral=True)


# ==========================================
# 3. SISTEMA DE VETOS
# ==========================================

@bot.hybrid_command(name="vetar", description="Prohíbe a un usuario inscribirse en los torneos de liga.")
async def vetar(ctx, usuario: discord.Member, *, razon: str = "Infracción grave en torneos"):
    guild = ctx.guild
    rol_vetado = guild.get_role(ROL_VETADO_ID)
    if not rol_vetado:
        await ctx.send("El rol de vetado configurado no existe en este servidor.", ephemeral=True)
        return
    
    try:
        await usuario.add_roles(rol_vetado, reason=razon)
        await ctx.send(f"🚫 **{usuario.mention}** ha sido **vetado** de los torneos de liga. Razón: {razon}")
        await enviar_log(guild, f"{usuario.mention} fue VETADO de los torneos por {ctx.author.mention}. Razón: {razon}")
    except Exception as e:
        await ctx.send(f"Error al asignar el rol de vetado: {e}")

@bot.hybrid_command(name="desvetar", description="Remueve el veto de torneos a un usuario.")
async def desvetar(ctx, usuario: discord.Member):
    guild = ctx.guild
    rol_vetado = guild.get_role(ROL_VETADO_ID)
    if not rol_vetado:
        await ctx.send("El rol de vetado configurado no existe en este servidor.", ephemeral=True)
        return
    
    try:
        await usuario.remove_roles(rol_vetado, reason="Remoción de veto por moderador")
        await ctx.send(f"✅ **{usuario.mention}** ya no está vetado y puede volver a inscribirse en los torneos.")
        await enviar_log(guild, f"A {usuario.mention} se le removió el veto de torneos por {ctx.author.mention}.")
    except Exception as e:
        await ctx.send(f"Error al remover el rol de vetado: {e}")


# ==========================================
# 4. TORNEO DE LIGAS (INSCRIPCIONES CON BOTONES Y FILA)
# ==========================================

class VistaInscripcionTorneo(discord.ui.View):
    def __init__(self, cupos_maximos: int):
        super().__init__(timeout=None)
        self.cupos_maximos = cupos_maximos
        self.inscritos = [] # Lista de discord.Member
        self.suplentes = [] # Lista de discord.Member

    def actualizar_embed(self):
        embed = discord.Embed(
            title="🏆 INSCRIPCIÓN ABIIERTA - TORNEO DE LIGA FC MOBILE",
            description=(
                f"Haz clic en el botón verde para asegurar tu cupo en el torneo del juego.\n"
                f"• **Cupos Principales:** {len(self.inscritos)} / {self.cupos_maximos}\n"
                f"• **Fila de Suplentes:** {len(self.suplentes)}"
            ),
            color=discord.Color.green()
        )

        # Mostrar lista de titulares
        titulares_txt = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(self.inscritos)]) if self.inscritos else "Ninguno todavía."
        embed.add_field(name="🟢 Titulares Principales", value=titulares_txt, inline=False)

        # Mostrar lista de suplentes / fila
        if self.suplentes:
            suplentes_txt = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(self.suplentes)])
            embed.add_field(name="🟡 Fila / Suplentes (En espera)", value=suplentes_txt, inline=False)

        embed.set_footer(text=f"Límite configurado: {self.cupos_maximos} participantes directos en el juego.")
        return embed

    @discord.ui.button(label="Inscribirse", style=discord.ButtonStyle.success, custom_id="btn_inscribir_torneo")
    async def inscribirse(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild

        # Verificar si tiene el rol de vetado
        rol_vetado = guild.get_role(ROL_VETADO_ID)
        if rol_vetado and rol_vetado in user.roles:
            await interaction.response.send_message("❌ Estás **vetado** de los torneos de liga y no puedes inscribirte.", ephemeral=True)
            return

        # Verificar si ya está inscrito en titulares o suplentes
        if user in self.inscritos or user in self.suplentes:
            await interaction.response.send_message("⚠️ Ya te encuentras registrado en este torneo.", ephemeral=True)
            return

        # Asignar a titular o suplente según cupos
        if len(self.inscritos) < self.cupos_maximos:
            self.inscritos.append(user)
            await interaction.response.send_message("✅ ¡Te has inscrito exitosamente como **Titular**!", ephemeral=True)
            await enviar_log(guild, f"{user.mention} se inscribió como **Titular** en el torneo de liga.")
        else:
            self.suplentes.append(user)
            await interaction.response.send_message("⚠️ Los cupos principales están llenos. Has entrado a la **Fila de Suplentes**.", ephemeral=True)
            await enviar_log(guild, f"{user.mention} entró a la **Fila de Suplentes** del torneo.")

        await interaction.message.edit(embed=self.actualizar_embed(), view=self)

    @discord.ui.button(label="Desinscribirse", style=discord.ButtonStyle.danger, custom_id="btn_desinscribir_torneo")
    async def desinscribirse(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild

        if user in self.inscritos:
            self.inscritos.remove(user)
            # Si hay suplentes, mover automáticamente al primero de la fila a titular
            if self.suplentes:
                nuevo_titular = self.suplentes.pop(0)
                self.inscritos.append(nuevo_titular)
                await enviar_log(guild, f"Se movió automáticamente a {nuevo_titular.mention} desde los suplentes a **Titular**.")
            
            await interaction.response.send_message("✅ Te has desinscrito del torneo correctamente.", ephemeral=True)
            await enviar_log(guild, f"{user.mention} se desinscritó del torneo de liga.")
            await interaction.message.edit(embed=self.actualizar_embed(), view=self)

        elif user in self.suplentes:
            self.suplentes.remove(user)
            await interaction.response.send_message("✅ Has salido de la lista de suplentes.", ephemeral=True)
            await enviar_log(guild, f"{user.mention} salió de la lista de suplentes del torneo.")
            await interaction.message.edit(embed=self.actualizar_embed(), view=self)
        else:
            await interaction.response.send_message("⚠️ No estabas inscrito en este torneo.", ephemeral=True)

@bot.hybrid_command(name="crear-inscripcion", description="Crea el panel de inscripciones con botones para el torneo.")
@app_commands.describe(cupos="Tamaño de los cupos principales del torneo en el juego")
@app_commands.choices(cupos=[
    app_commands.Choice(name="4 Jugadores", value=4),
    app_commands.Choice(name="8 Jugadores", value=8),
    app_commands.Choice(name="16 Jugadores", value=16),
    app_commands.Choice(name="32 Jugadores", value=32),
])
async def crear_inscripcion(ctx, cupos: int):
    vista = VistaInscripcionTorneo(cupos_maximos=cupos)
    embed = vista.actualizar_embed()
    
    await ctx.send(embed=embed, view=vista)
    if ctx.interaction:
        await ctx.interaction.response.send_message("Panel de inscripción creado con éxito.", ephemeral=True)
    
    await enviar_log(ctx.guild, f"El moderador {ctx.author.mention} creó un panel de inscripción para el torneo ({cupos} cupos principales).")

# Ejecutar el bot utilizando la variable de entorno segura de Render
TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN)
