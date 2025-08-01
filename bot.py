import os
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
from collections import deque
import asyncio
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Print de la version de discord.py
print("Version de discord.py:", discord.__version__)

# Vérification du token
if not TOKEN:
    print("❌ ERREUR: Token Discord manquant!")
    print("Créez un fichier .env avec:")
    print("TOKEN=votre_token_discord_ici")
    print("\nOu définissez la variable d'environnement TOKEN")
    exit(1)

# Configuration du bot avec les intents requis
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Bot setup avec slash commands
bot = commands.Bot(command_prefix="$", intents=intents)

# File d'attente par serveur
SONG_QUEUES = {}

# Timers de déconnexion automatique par serveur
DISCONNECT_TIMERS = {}

# Délai avant déconnexion automatique (en secondes)
AUTO_DISCONNECT_DELAY = 300  # 5 minutes

# Configuration yt-dlp moderne
YDL_OPTIONS = {
    "format": "bestaudio[ext=webm]/bestaudio/best",
    "noplaylist": True,
    "extractaudio": True,
    "audioformat": "webm",
    "quiet": True,
    "no_warnings": True,
    "ignoreerrors": True,
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web"],
            "skip": ["hls"]
        }
    }
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 2",
    "options": "-vn -bufsize 64k",
}

# Fonctions de gestion de la déconnexion automatique
def cancel_disconnect_timer(guild_id):
    """Annule le timer de déconnexion pour un serveur"""
    if guild_id in DISCONNECT_TIMERS:
        DISCONNECT_TIMERS[guild_id].cancel()
        del DISCONNECT_TIMERS[guild_id]
        print(f"⏹️ Timer de déconnexion annulé pour {guild_id}")

async def auto_disconnect(guild_id):
    """Déconnecte automatiquement le bot après inactivité"""
    try:
        await asyncio.sleep(AUTO_DISCONNECT_DELAY)
        
        # Vérifier si le bot est encore connecté et inactif
        guild = bot.get_guild(int(guild_id))
        if guild and guild.voice_client:
            voice_client = guild.voice_client
            
            # Vérifier si vraiment inactif (pas de musique + queue vide)
            if (not voice_client.is_playing() and 
                not voice_client.is_paused() and 
                (guild_id not in SONG_QUEUES or len(SONG_QUEUES[guild_id]) == 0)):
                
                # Nettoyer la queue
                if guild_id in SONG_QUEUES:
                    SONG_QUEUES[guild_id].clear()
                
                # Déconnexion
                await voice_client.disconnect()
                print(f"🚪 Déconnexion automatique: inactivité de {AUTO_DISCONNECT_DELAY//60} minutes")
                
                # Trouver un canal pour envoyer le message
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        try:
                            await channel.send(f"🚪 **Déconnexion automatique** après {AUTO_DISCONNECT_DELAY//60} minutes d'inactivité.")
                            break
                        except:
                            continue
        
        # Nettoyer le timer
        if guild_id in DISCONNECT_TIMERS:
            del DISCONNECT_TIMERS[guild_id]
            
    except asyncio.CancelledError:
        # Timer annulé (normal)
        pass
    except Exception as e:
        print(f"Erreur déconnexion auto: {e}")

def start_disconnect_timer(guild_id):
    """Démarre un timer de déconnexion automatique"""
    # Annuler l'ancien timer s'il existe
    cancel_disconnect_timer(guild_id)
    
    # Créer un nouveau timer
    timer = asyncio.create_task(auto_disconnect(guild_id))
    DISCONNECT_TIMERS[guild_id] = timer
    print(f"⏰ Timer de déconnexion démarré: {AUTO_DISCONNECT_DELAY//60} minutes")

# Fonction asynchrone pour éviter le blocage avec yt-dlp
async def get_audio_info_async(url_or_query):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _get_audio_info(url_or_query))

def _get_audio_info(url_or_query):
    """Extrait les informations audio avec yt-dlp"""
    try:
        # Si ce n'est pas une URL YouTube, on fait une recherche
        if not url_or_query.startswith('http'):
            query = f"ytsearch1:{url_or_query}"
        else:
            query = url_or_query
        
        # Utiliser yt-dlp pour extraire les infos
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            
            # Si c'est une recherche, prendre le premier résultat
            if 'entries' in info and info['entries']:
                info = info['entries'][0]
            
            if not info:
                return None
                
            return {
                'url': info.get('url'),
                'title': info.get('title', 'Sans titre'),
                'duration': info.get('duration', 0)
            }
        
    except Exception as e:
        print(f"Erreur yt-dlp: {e}")
        return None


# Événement d'initialisation du bot
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} connecté")

@bot.event
async def on_voice_state_update(member, before, after):
    # Si le bot est seul dans le canal, le garder connecté mais arrêter la musique
    if member == bot.user:
        return
    
    voice_client = member.guild.voice_client
    if voice_client and voice_client.channel:
        # Compter les membres non-bots dans le canal
        members = [m for m in voice_client.channel.members if not m.bot]
        if len(members) == 0:
            # Arrêter la musique mais rester connecté
            if voice_client.is_playing():
                voice_client.stop()
            guild_id = str(member.guild.id)
            if guild_id in SONG_QUEUES:
                SONG_QUEUES[guild_id].clear()


# Fonction pour jouer la chanson suivante
async def play_next_song(voice_client, guild_id, channel):
    try:
        if not voice_client.is_connected():
            return
            
        if SONG_QUEUES[guild_id]:
            # Annuler le timer de déconnexion puisqu'on a de la musique
            cancel_disconnect_timer(guild_id)
            
            audio_url, title = SONG_QUEUES[guild_id].popleft()

            source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)

            def after_play(error):
                if error:
                    print(f"Erreur lors de la lecture de {title}: {error}")
                if voice_client.is_connected():
                    asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

            voice_client.play(source, after=after_play)
            await channel.send(f"🎵 **En cours de lecture:** {title}")
        else:
            # Queue vide - démarrer le timer de déconnexion automatique
            start_disconnect_timer(guild_id)
            await channel.send(f"📭 **File d'attente terminée** - Déconnexion automatique dans {AUTO_DISCONNECT_DELAY//60} minutes")
    except Exception as e:
        print(f"Erreur dans play_next_song: {e}")
        if voice_client.is_connected():
            await voice_client.disconnect()


# Commandes slash modernes

@bot.tree.command(name="play", description="Joue de la musique depuis YouTube")
@app_commands.describe(recherche="Recherche YouTube ou URL")
async def play(interaction: discord.Interaction, recherche: str):
    await interaction.response.defer()

    # Vérifier si l'utilisateur est dans un canal vocal
    if interaction.user.voice is None:
        await interaction.followup.send("🔊 **Vous devez être dans un canal vocal pour jouer de la musique.**")
        return
    
    voice_channel = interaction.user.voice.channel

    if voice_channel is None:
        await interaction.followup.send("🔊 **Vous devez être dans un canal vocal pour jouer de la musique.**")
        return

    voice_client = interaction.guild.voice_client

    if voice_client is None:
        # Workaround optimisé pour le bug Discord 4006 global
        # Force Discord à changer d'endpoint rapidement
        max_retries = 4
        for attempt in range(max_retries):
            try:
                # Timeouts très courts pour forcer le changement d'endpoint rapidement
                timeout = 4.0 + (attempt * 1.5)  # 4s, 5.5s, 7s, 8.5s
                print(f"🔄 Tentative connexion {attempt + 1}/{max_retries} (timeout: {timeout}s)")
                voice_client = await voice_channel.connect(timeout=timeout, reconnect=True)
                print(f"✅ Connexion vocale réussie ! (tentative {attempt + 1})")
                break
            except Exception as e:
                print(f"❌ Tentative {attempt + 1}: {str(e)[:100]}...")
                if attempt == max_retries - 1:
                    await interaction.followup.send(f"❌ **Connexion impossible après {max_retries} tentatives**\n💡 **Bug Discord global** - Endpoint `c-cdg11` défaillant, réessayez")
                    return
                # Délai court pour forcer changement d'endpoint
                await asyncio.sleep(0.8 + attempt * 0.3)
    elif voice_channel != voice_client.channel:
        try:
            await voice_client.move_to(voice_channel)
        except Exception as e:
            await interaction.followup.send(f"❌ **Impossible de changer de canal vocal:** {str(e)}")
            return

    # Recherche avec pytube
    try:
        result = await get_audio_info_async(recherche)
        
        if result is None:
            await interaction.followup.send("❌ **Aucun résultat trouvé.**")
            return

        audio_url = result["url"]
        title = result["title"]
    except Exception as e:
        await interaction.followup.send(f"❌ **Erreur lors de la recherche:** {str(e)}")
        return

    guild_id = str(interaction.guild_id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()

    # Annuler le timer de déconnexion puisqu'on ajoute de la musique
    cancel_disconnect_timer(guild_id)

    SONG_QUEUES[guild_id].append((audio_url, title))

    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"✅ **Ajouté à la file d'attente:** {title}")
    else:
        await interaction.followup.send(f"🎵 **En cours de lecture:** {title}")
        await play_next_song(voice_client, guild_id, interaction.channel)


@bot.tree.command(name="pause", description="Met en pause la musique")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        return await interaction.response.send_message("❌ **Je ne suis pas dans un canal vocal.**")

    if not voice_client.is_playing():
        return await interaction.response.send_message("❌ **Rien n'est en cours de lecture.**")
    
    voice_client.pause()
    await interaction.response.send_message("⏸️ **Lecture mise en pause !**")


@bot.tree.command(name="resume", description="Reprend la lecture")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        return await interaction.response.send_message("❌ **Je ne suis pas dans un canal vocal.**")

    if not voice_client.is_paused():
        return await interaction.response.send_message("❌ **Je ne suis pas en pause.**")
    
    voice_client.resume()
    await interaction.response.send_message("▶️ **Lecture reprise !**")


@bot.tree.command(name="skip", description="Passe à la chanson suivante")
async def skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        voice_client.stop()
        await interaction.response.send_message("⏭️ **Chanson passée.**")
    else:
        await interaction.response.send_message("❌ **Rien à passer.**")


@bot.tree.command(name="stop", description="Arrête la musique et vide la file d'attente")
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    if not voice_client or not voice_client.is_connected():
        return await interaction.response.send_message("❌ **Je ne suis pas connecté à un canal vocal.**")

    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    # Démarrer le timer de déconnexion automatique
    start_disconnect_timer(guild_id_str)

    await interaction.response.send_message(f"⏹️ **Arrêt de la lecture !** Déconnexion automatique dans {AUTO_DISCONNECT_DELAY//60} minutes.")


@bot.tree.command(name="queue", description="Affiche la file d'attente")
async def queue(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    
    if guild_id not in SONG_QUEUES or len(SONG_QUEUES[guild_id]) == 0:
        await interaction.response.send_message("📭 **La file d'attente est vide.**")
        return

    queue_list = "**🎶 FILE D'ATTENTE**\n\n"
    for i, (_, title) in enumerate(list(SONG_QUEUES[guild_id])[:10]):
        queue_list += f"**{i + 1}.** {title}\n"
    
    if len(SONG_QUEUES[guild_id]) > 10:
        queue_list += f"\n... et {len(SONG_QUEUES[guild_id]) - 10} autres"
    
    await interaction.response.send_message(queue_list)


@bot.tree.command(name="leave", description="Déconnecte le bot du canal vocal")
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    if not voice_client or not voice_client.is_connected():
        await interaction.response.send_message("❌ **Je ne suis pas connecté à un canal vocal.**")
        return

    guild_id_str = str(interaction.guild_id)
    
    # Annuler le timer de déconnexion
    cancel_disconnect_timer(guild_id_str)
    
    # Nettoyer la queue
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    await voice_client.disconnect()
    await interaction.response.send_message("👋 **Déconnexion du canal vocal !**")





# Point d'entrée de l'application
bot.run(TOKEN)
