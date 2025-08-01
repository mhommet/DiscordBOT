import os
import discord
from discord.ext import commands
from discord import app_commands
from pytube import YouTube
from pytube.exceptions import PytubeError
import requests
import re
from collections import deque
import asyncio
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Configuration du bot avec les intents requis
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Bot setup avec slash commands optimisé pour WSL
bot = commands.Bot(
    command_prefix="$", 
    intents=intents,
    heartbeat_timeout=60.0,
    guild_ready_timeout=5.0,
    max_messages=None
)

# File d'attente par serveur
SONG_QUEUES = {}

# Simple YouTube search function
def search_youtube(query):
    """Recherche YouTube simple via l'API de recherche"""
    search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    try:
        response = requests.get(search_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=10)
        
        # Extract video IDs from the response
        video_ids = re.findall(r'"videoId":"([^"]+)"', response.text)
        if video_ids:
            return f"https://www.youtube.com/watch?v={video_ids[0]}"
    except (requests.RequestException, ValueError, AttributeError):
        pass
    return None

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -ar 48000 -ac 2 -b:a 96k",
}

# Fonction asynchrone pour éviter le blocage avec pytube
async def get_audio_info_async(url_or_query):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _get_audio_info(url_or_query))

def _get_audio_info(url_or_query):
    """Extrait les informations audio avec pytube"""
    try:
        # Si ce n'est pas une URL YouTube, on fait une recherche
        if not url_or_query.startswith('http'):
            url = search_youtube(url_or_query)
            if not url:
                return None
        else:
            url = url_or_query
        
        # Utiliser pytube pour extraire les infos
        yt = YouTube(url)
        
        # Obtenir le meilleur stream audio
        audio_stream = yt.streams.filter(only_audio=True, file_extension='webm').first()
        if not audio_stream:
            audio_stream = yt.streams.filter(only_audio=True).first()
        
        if not audio_stream:
            return None
            
        return {
            'url': audio_stream.url,
            'title': yt.title,
            'duration': yt.length
        }
        
    except PytubeError as e:
        print(f"Erreur pytube: {e}")
        return None
    except (requests.RequestException, ValueError, AttributeError) as e:
        print(f"Erreur générale: {e}")
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
            audio_url, title = SONG_QUEUES[guild_id].popleft()

            source = discord.FFmpegOpusAudio(audio_url, **FFMPEG_OPTIONS)

            def after_play(error):
                if error:
                    print(f"Erreur lors de la lecture de {title}: {error}")
                if voice_client.is_connected():
                    asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

            voice_client.play(source, after=after_play)
            await channel.send(f"🎵 **En cours de lecture:** {title}")
        # Ne plus déconnecter automatiquement quand la queue est vide
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
        try:
            # Configuration spéciale pour WSL
            voice_client = await voice_channel.connect(timeout=30.0, reconnect=False)
            await asyncio.sleep(1)  # Attendre stabilisation sur WSL
        except Exception as e:
            await interaction.followup.send(f"❌ **Impossible de se connecter au canal vocal:** {str(e)}")
            return
    elif voice_channel != voice_client.channel:
        try:
            await voice_client.move_to(voice_channel)
            await asyncio.sleep(0.5)  # Attendre déplacement
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
    except (PytubeError, requests.RequestException, ValueError, AttributeError) as e:
        await interaction.followup.send(f"❌ **Erreur lors de la recherche:** {str(e)}")
        return

    guild_id = str(interaction.guild_id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()

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

    await interaction.response.send_message("⏹️ **Arrêt de la lecture ! Utilisez /leave pour me déconnecter.**")


@bot.tree.command(name="leave", description="Déconnecte le bot du canal vocal")
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    if not voice_client or not voice_client.is_connected():
        return await interaction.response.send_message("❌ **Je ne suis pas connecté à un canal vocal.**")

    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    await voice_client.disconnect()
    await interaction.response.send_message("👋 **Déconnexion du canal vocal !**")


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


# Point d'entrée de l'application
bot.run(TOKEN)
