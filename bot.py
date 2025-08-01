import os
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
from collections import deque
import asyncio
from dotenv import load_dotenv
import aiohttp
import random
import re
import json
import sqlite3
from datetime import datetime, timedelta

# Chargement des variables d'environnement
load_dotenv()
TOKEN = os.getenv("TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")  # Optionnel
BLAGUES_API_TOKEN = os.getenv("BLAGUES_API_TOKEN")  # Optionnel pour blagues françaises

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

# Timers de rappels actifs
REMINDER_TIMERS = {}

# Limite quotidienne OpenWeather API (1000 appels gratuits)
OPENWEATHER_DAILY_LIMIT = 1000

# Répertoire des données persistantes
DATA_DIR = "/app/data"
OPENWEATHER_USAGE_FILE = f"{DATA_DIR}/openweather_usage.json"

# Base de données SQLite
DATABASE_FILE = f"{DATA_DIR}/bot_data.db"

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
    print(f'{bot.user} est connecté à Discord!')
    
    # Initialiser la base de données
    init_database()
    
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commandes synchronisées')
    except Exception as e:
        print(f'❌ Erreur lors de la synchronisation: {e}')

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

@bot.event
async def on_message(message):
    """Event pour logger les messages et ajouter de l'XP"""
    if message.author.bot:
        return
    
    # Logger le message pour les stats
    log_message(message)
    
    # Ajouter de l'XP (cooldown simple avec timestamp)
    user_id = str(message.author.id)
    now = datetime.now()
    
    # Vérifier si l'utilisateur peut gagner de l'XP (cooldown de 60 secondes)
    if not hasattr(bot, '_xp_cooldowns'):
        bot._xp_cooldowns = {}
    
    last_xp_time = bot._xp_cooldowns.get(user_id)
    if not last_xp_time or (now - last_xp_time).total_seconds() >= 60:
        # Calculer l'XP basé sur la longueur du message
        xp_gain = min(15 + len(message.content) // 10, 50)  # Entre 15 et 50 XP
        old_level = get_user_xp(message.author.id)["level"]
        new_level = add_user_xp(message.author, xp_gain)
        
        # Féliciter si montée de niveau
        if new_level > old_level:
            embed = discord.Embed(
                title="🎉 Montée de niveau !",
                description=f"**{message.author.display_name}** est maintenant niveau **{new_level}** !",
                color=0xffd700
            )
            embed.add_field(name="🏆 Nouveau niveau", value=f"`{new_level}`", inline=True)
            embed.add_field(name="✨ XP gagné", value=f"`+{xp_gain}`", inline=True)
            
            try:
                await message.channel.send(embed=embed, delete_after=10)
            except:
                pass  # Ignorer si pas de permission
        
        bot._xp_cooldowns[user_id] = now
    
    # Traiter les commandes
    await bot.process_commands(message)


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





# ==================== COMMANDES CRYPTO ====================

async def get_crypto_price(crypto_id):
    """Récupère le prix d'une crypto via l'API CoinGecko"""
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies=usd,eur&include_24hr_change=true"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get(crypto_id)
                else:
                    return None
    except Exception as e:
        print(f"Erreur API crypto: {e}")
        return None

@bot.tree.command(name="btc", description="Affiche le prix du Bitcoin")
async def btc_price(interaction: discord.Interaction):
    await interaction.response.defer()
    
    data = await get_crypto_price("bitcoin")
    
    if not data:
        await interaction.followup.send("❌ **Impossible de récupérer le prix du Bitcoin**")
        return
    
    price_usd = data.get('usd', 0)
    price_eur = data.get('eur', 0)
    change_24h = data.get('usd_24h_change', 0)
    
    # Emoji selon la tendance
    trend_emoji = "📈" if change_24h > 0 else "📉" if change_24h < 0 else "➡️"
    change_color = 0x00ff00 if change_24h > 0 else 0xff0000 if change_24h < 0 else 0xffff00
    
    embed = discord.Embed(
        title="₿ Bitcoin (BTC)",
        color=change_color,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="💵 Prix USD", value=f"${price_usd:,.2f}", inline=True)
    embed.add_field(name="💶 Prix EUR", value=f"€{price_eur:,.2f}", inline=True)
    embed.add_field(name=f"{trend_emoji} 24h", value=f"{change_24h:+.2f}%", inline=True)
    embed.set_footer(text="Source: CoinGecko")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="eth", description="Affiche le prix d'Ethereum")
async def eth_price(interaction: discord.Interaction):
    await interaction.response.defer()
    
    data = await get_crypto_price("ethereum")
    
    if not data:
        await interaction.followup.send("❌ **Impossible de récupérer le prix d'Ethereum**")
        return
    
    price_usd = data.get('usd', 0)
    price_eur = data.get('eur', 0)
    change_24h = data.get('usd_24h_change', 0)
    
    # Emoji selon la tendance
    trend_emoji = "📈" if change_24h > 0 else "📉" if change_24h < 0 else "➡️"
    change_color = 0x00ff00 if change_24h > 0 else 0xff0000 if change_24h < 0 else 0xffff00
    
    embed = discord.Embed(
        title="⧫ Ethereum (ETH)",
        color=change_color,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="💵 Prix USD", value=f"${price_usd:,.2f}", inline=True)
    embed.add_field(name="💶 Prix EUR", value=f"€{price_eur:,.2f}", inline=True)
    embed.add_field(name=f"{trend_emoji} 24h", value=f"{change_24h:+.2f}%", inline=True)
    embed.set_footer(text="Source: CoinGecko")
    
    await interaction.followup.send(embed=embed)


# ==================== GESTION OPENWEATHER API ====================

def load_openweather_usage():
    """Charge les données d'utilisation OpenWeather"""
    try:
        # Assurer que le répertoire existe
        ensure_data_directory()
        
        with open(OPENWEATHER_USAGE_FILE, 'r') as f:
            data = json.load(f)
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Reset si nouvelle journée
            if data.get("date") != today:
                return {"date": today, "calls": 0}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        today = datetime.now().strftime("%Y-%m-%d")
        return {"date": today, "calls": 0}

def save_openweather_usage(usage_data):
    """Sauvegarde les données d'utilisation OpenWeather"""
    try:
        # Assurer que le répertoire existe
        ensure_data_directory()
        
        with open(OPENWEATHER_USAGE_FILE, 'w') as f:
            json.dump(usage_data, f)
    except Exception as e:
        print(f"Erreur sauvegarde usage OpenWeather: {e}")

def can_use_openweather():
    """Vérifie si on peut utiliser OpenWeather API"""
    if not OPENWEATHER_API_KEY:
        return False
    
    usage = load_openweather_usage()
    return usage["calls"] < OPENWEATHER_DAILY_LIMIT

def increment_openweather_usage():
    """Incrémente le compteur d'usage OpenWeather"""
    usage = load_openweather_usage()
    usage["calls"] += 1
    save_openweather_usage(usage)
    return usage

# ==================== BASE DE DONNÉES SQLITE ====================

def ensure_data_directory():
    """Crée le répertoire de données s'il n'existe pas"""
    try:
        import os
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            print(f"✅ Répertoire de données créé: {DATA_DIR}")
    except Exception as e:
        print(f"❌ Erreur création répertoire de données: {e}")

def init_database():
    """Initialise la base de données SQLite"""
    try:
        # Assurer que le répertoire existe
        ensure_data_directory()
        
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Table des utilisateurs pour XP/niveaux
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                discriminator TEXT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages_count INTEGER DEFAULT 0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table des messages pour statistiques
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                content_length INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hour INTEGER,
                day_of_week INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Table des commandes utilisées
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                command_name TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        conn.commit()
        conn.close()
        print("✅ Base de données initialisée")
        
    except Exception as e:
        print(f"❌ Erreur initialisation base de données: {e}")

def get_user_xp(user_id):
    """Récupère l'XP et le niveau d'un utilisateur"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT xp, level, messages_count FROM users WHERE user_id = ?", (str(user_id),))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {"xp": result[0], "level": result[1], "messages": result[2]}
        else:
            return {"xp": 0, "level": 1, "messages": 0}
            
    except Exception as e:
        print(f"Erreur récupération XP: {e}")
        return {"xp": 0, "level": 1, "messages": 0}

def add_user_xp(user, xp_gain=15):
    """Ajoute de l'XP à un utilisateur et met à jour son niveau"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        user_id = str(user.id)
        username = user.display_name
        discriminator = getattr(user, 'discriminator', '0000')
        
        # Insérer ou mettre à jour l'utilisateur
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, discriminator, xp, level, messages_count)
            VALUES (?, ?, ?, 0, 1, 0)
        """, (user_id, username, discriminator))
        
        # Mettre à jour XP et compteur de messages
        cursor.execute("""
            UPDATE users 
            SET xp = xp + ?, 
                messages_count = messages_count + 1,
                username = ?,
                discriminator = ?,
                last_activity = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (xp_gain, username, discriminator, user_id))
        
        # Récupérer l'XP actuel pour calculer le niveau
        cursor.execute("SELECT xp FROM users WHERE user_id = ?", (user_id,))
        current_xp = cursor.fetchone()[0]
        
        # Calcul du niveau (100 XP par niveau + 50 XP supplémentaires par niveau)
        # Niveau 1: 0-99 XP, Niveau 2: 100-249 XP, Niveau 3: 250-449 XP, etc.
        new_level = 1
        xp_needed = 100
        total_xp_needed = 0
        
        while current_xp >= total_xp_needed + xp_needed:
            total_xp_needed += xp_needed
            new_level += 1
            xp_needed += 50  # Augmente de 50 XP par niveau
        
        # Mettre à jour le niveau si nécessaire
        cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, user_id))
        
        conn.commit()
        conn.close()
        
        return new_level
        
    except Exception as e:
        print(f"Erreur ajout XP: {e}")
        return 1

def log_message(message):
    """Enregistre un message pour les statistiques"""
    try:
        if message.author.bot:
            return
            
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        now = datetime.now()
        
        cursor.execute("""
            INSERT INTO messages (user_id, guild_id, channel_id, message_id, content_length, hour, day_of_week)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(message.author.id),
            str(message.guild.id) if message.guild else "DM",
            str(message.channel.id),
            str(message.id),
            len(message.content),
            now.hour,
            now.weekday()
        ))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Erreur log message: {e}")

def log_command_usage(user_id, command_name, guild_id):
    """Enregistre l'utilisation d'une commande"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO command_usage (user_id, command_name, guild_id)
            VALUES (?, ?, ?)
        """, (str(user_id), command_name, str(guild_id)))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Erreur log commande: {e}")

# ==================== COMMANDES MÉTÉO ====================

async def get_weather(city):
    """Récupère la météo via l'API OpenWeatherMap ou wttr.in avec limitation quotidienne"""
    try:
        use_openweather = can_use_openweather()
        
        if use_openweather:
            # API OpenWeatherMap (plus précise)
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        # Incrémenter le compteur d'usage
                        usage = increment_openweather_usage()
                        data = await response.json()
                        # Ajouter info sur la source
                        data["_source"] = "openweather"
                        data["_usage"] = usage
                        return data
                    else:
                        # Fallback vers wttr.in si erreur
                        print(f"Erreur OpenWeather {response.status}, fallback vers wttr.in")
                        use_openweather = False
        
        if not use_openweather:
            # API wttr.in (fallback gratuite)
            url = f"https://wttr.in/{city}?format=j1"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Ajouter info sur la source
                        data["_source"] = "wttr"
                        return data
                    else:
                        return None
                        
    except Exception as e:
        print(f"Erreur API météo: {e}")
        return None

def get_weather_emoji(condition):
    """Retourne un emoji selon les conditions météo"""
    condition = condition.lower()
    if "clear" in condition or "ensoleillé" in condition:
        return "☀️"
    elif "cloud" in condition or "nuage" in condition:
        return "☁️"
    elif "rain" in condition or "pluie" in condition:
        return "🌧️"
    elif "snow" in condition or "neige" in condition:
        return "❄️"
    elif "storm" in condition or "orage" in condition:
        return "⛈️"
    elif "fog" in condition or "brouillard" in condition:
        return "🌫️"
    else:
        return "🌤️"

@bot.tree.command(name="weather", description="Affiche la météo d'une ville")
@app_commands.describe(ville="Nom de la ville")
async def weather(interaction: discord.Interaction, ville: str):
    await interaction.response.defer()
    
    data = await get_weather(ville)
    
    if not data:
        await interaction.followup.send(f"❌ **Météo introuvable pour:** {ville}")
        return
    
    source = data.get("_source", "unknown")
    
    if source == "openweather":
        # Format OpenWeatherMap
        city_name = data['name']
        country = data['sys']['country']
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        humidity = data['main']['humidity']
        description = data['weather'][0]['description'].title()
        emoji = get_weather_emoji(description)
        
        # Informations d'usage API
        usage = data.get("_usage", {})
        calls_today = usage.get("calls", 0)
        remaining_calls = OPENWEATHER_DAILY_LIMIT - calls_today
        
    else:
        # Format wttr.in
        current = data['current_condition'][0]
        city_name = ville.title()
        country = ""
        temp = int(current['temp_C'])
        feels_like = int(current['FeelsLikeC'])
        humidity = int(current['humidity'])
        description = current['weatherDesc'][0]['value']
        emoji = get_weather_emoji(description)
        calls_today = 0
        remaining_calls = 0
    
    embed = discord.Embed(
        title=f"{emoji} Météo de {city_name}{f', {country}' if country else ''}",
        description=description,
        color=0x87CEEB,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="🌡️ Température", value=f"{temp}°C", inline=True)
    embed.add_field(name="🤔 Ressenti", value=f"{feels_like}°C", inline=True)
    embed.add_field(name="💧 Humidité", value=f"{humidity}%", inline=True)
    
    # Footer avec informations sur la source et l'usage
    if source == "openweather":
        footer_text = f"Source: OpenWeatherMap • {calls_today}/{OPENWEATHER_DAILY_LIMIT} appels utilisés"
        if remaining_calls <= 100:
            footer_text += f" ⚠️ {remaining_calls} restants"
    elif source == "wttr":
        if OPENWEATHER_API_KEY:
            usage = load_openweather_usage()
            calls_today = usage.get("calls", 0)
            footer_text = f"Source: wttr.in (fallback) • OpenWeather: {calls_today}/{OPENWEATHER_DAILY_LIMIT} utilisés"
        else:
            footer_text = "Source: wttr.in • Ajoutez OPENWEATHER_API_KEY pour plus de précision"
    else:
        footer_text = "Source: inconnue"
    
    embed.set_footer(text=footer_text)
    
    await interaction.followup.send(embed=embed)


# ==================== MINI-JEUX ====================

@bot.tree.command(name="pfc", description="Joue à Pierre-Feuille-Ciseaux contre le bot")
@app_commands.describe(choix="Votre choix: pierre, feuille ou ciseaux")
@app_commands.choices(choix=[
    app_commands.Choice(name="🪨 Pierre", value="pierre"),
    app_commands.Choice(name="📄 Feuille", value="feuille"),
    app_commands.Choice(name="✂️ Ciseaux", value="ciseaux")
])
async def rock_paper_scissors(interaction: discord.Interaction, choix: app_commands.Choice[str]):
    choices = ["pierre", "feuille", "ciseaux"]
    emojis = {"pierre": "🪨", "feuille": "📄", "ciseaux": "✂️"}
    
    user_choice = choix.value
    bot_choice = random.choice(choices)
    
    user_emoji = emojis[user_choice]
    bot_emoji = emojis[bot_choice]
    
    # Déterminer le gagnant
    if user_choice == bot_choice:
        result = "🤝 **Égalité !**"
        color = 0xffff00
    elif (user_choice == "pierre" and bot_choice == "ciseaux") or \
         (user_choice == "feuille" and bot_choice == "pierre") or \
         (user_choice == "ciseaux" and bot_choice == "feuille"):
        result = "🎉 **Vous gagnez !**"
        color = 0x00ff00
    else:
        result = "😢 **Vous perdez !**"
        color = 0xff0000
    
    embed = discord.Embed(
        title="🎮 Pierre-Feuille-Ciseaux",
        description=result,
        color=color
    )
    
    embed.add_field(name="👤 Votre choix", value=f"{user_emoji} {user_choice.title()}", inline=True)
    embed.add_field(name="🤖 Choix du bot", value=f"{bot_emoji} {bot_choice.title()}", inline=True)
    embed.add_field(name="📋 Règles", value="Pierre bat Ciseaux\nFeuille bat Pierre\nCiseaux bat Feuille", inline=False)
    
    await interaction.response.send_message(embed=embed)


# ==================== SYSTÈME DE SONDAGES ====================

@bot.tree.command(name="poll", description="Crée un sondage avec réactions")
@app_commands.describe(
    question="La question du sondage",
    option1="Première option",
    option2="Deuxième option", 
    option3="Troisième option (optionnel)",
    option4="Quatrième option (optionnel)",
    option5="Cinquième option (optionnel)"
)
async def create_poll(
    interaction: discord.Interaction, 
    question: str,
    option1: str,
    option2: str,
    option3: str = None,
    option4: str = None,
    option5: str = None
):
    # Réactions emojis pour les options
    reactions = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    
    # Collecter les options non-nulles
    options = [option1, option2]
    if option3: options.append(option3)
    if option4: options.append(option4) 
    if option5: options.append(option5)
    
    if len(options) > 5:
        await interaction.response.send_message("❌ **Maximum 5 options autorisées !**", ephemeral=True)
        return
    
    # Créer l'embed du sondage
    embed = discord.Embed(
        title="📊 Sondage",
        description=f"**{question}**",
        color=0x3498db,
        timestamp=discord.utils.utcnow()
    )
    
    # Ajouter les options
    poll_text = ""
    for i, option in enumerate(options):
        poll_text += f"{reactions[i]} {option}\n"
    
    embed.add_field(name="Options:", value=poll_text, inline=False)
    embed.set_footer(text=f"Sondage créé par {interaction.user.display_name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    
    # Envoyer le sondage
    await interaction.response.send_message(embed=embed)
    
    # Récupérer le message pour ajouter les réactions
    message = await interaction.original_response()
    
    # Ajouter les réactions
    for i in range(len(options)):
        await message.add_reaction(reactions[i])

@bot.tree.command(name="quickpoll", description="Sondage rapide Oui/Non")
@app_commands.describe(question="La question du sondage")
async def quick_poll(interaction: discord.Interaction, question: str):
    embed = discord.Embed(
        title="📊 Sondage rapide",
        description=f"**{question}**",
        color=0x2ecc71,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="Options:", value="✅ Oui\n❌ Non", inline=False)
    embed.set_footer(text=f"Sondage créé par {interaction.user.display_name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    
    # Ajouter réactions Oui/Non
    await message.add_reaction("✅")
    await message.add_reaction("❌")


# ==================== SYSTÈME DE RAPPELS ====================

def parse_duration(duration_str):
    """Parse une durée comme '5m', '2h', '1d' en secondes"""
    try:
        match = re.match(r'(\d+)([smhd])', duration_str.lower())
        if not match:
            return None
        
        amount, unit = match.groups()
        amount = int(amount)
        
        multipliers = {
            's': 1,           # secondes
            'm': 60,          # minutes
            'h': 3600,        # heures
            'd': 86400        # jours
        }
        
        return amount * multipliers.get(unit, 0)
    except:
        return None

def format_duration(seconds):
    """Formate une durée en secondes vers un format lisible"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds//60}m {seconds%60}s"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"

async def send_reminder(user_id, channel_id, message, reminder_id):
    """Envoie un rappel après le délai"""
    try:
        # Attendre le délai
        await asyncio.sleep(REMINDER_TIMERS[reminder_id]['delay'])
        
        # Vérifier si le rappel n'a pas été annulé
        if reminder_id not in REMINDER_TIMERS:
            return
            
        # Récupérer le canal et l'utilisateur
        channel = bot.get_channel(channel_id)
        user = bot.get_user(user_id)
        
        if channel and user:
            embed = discord.Embed(
                title="⏰ Rappel",
                description=f"**{message}**",
                color=0xf39c12,
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text=f"Rappel pour {user.display_name}", icon_url=user.avatar.url if user.avatar else None)
            
            await channel.send(f"{user.mention}", embed=embed)
        
        # Nettoyer le timer
        if reminder_id in REMINDER_TIMERS:
            del REMINDER_TIMERS[reminder_id]
            
    except asyncio.CancelledError:
        # Timer annulé
        pass
    except Exception as e:
        print(f"Erreur rappel: {e}")

@bot.tree.command(name="remindme", description="Programme un rappel personnel")
@app_commands.describe(
    duration="Durée (ex: 5m, 2h, 1d)",
    message="Message du rappel"
)
async def remind_me(interaction: discord.Interaction, duration: str, message: str):
    seconds = parse_duration(duration)
    
    if not seconds:
        await interaction.response.send_message("❌ **Format de durée invalide !** Utilisez: `5m`, `2h`, `1d`", ephemeral=True)
        return
    
    if seconds > 86400 * 7:  # Max 7 jours
        await interaction.response.send_message("❌ **Durée maximale: 7 jours !**", ephemeral=True)
        return
    
    # Créer un ID unique pour le rappel
    reminder_id = f"{interaction.user.id}_{datetime.now().timestamp()}"
    
    # Créer le timer
    timer_task = asyncio.create_task(send_reminder(
        interaction.user.id, 
        interaction.channel.id, 
        message, 
        reminder_id
    ))
    
    REMINDER_TIMERS[reminder_id] = {
        'task': timer_task,
        'delay': seconds,
        'user_id': interaction.user.id,
        'message': message
    }
    
    # Calculer l'heure du rappel
    remind_time = datetime.now() + timedelta(seconds=seconds)
    
    embed = discord.Embed(
        title="⏰ Rappel programmé",
        description=f"**Message:** {message}",
        color=0x3498db
    )
    embed.add_field(name="⏱️ Dans", value=format_duration(seconds), inline=True)
    embed.add_field(name="📅 Le", value=remind_time.strftime("%d/%m/%Y à %H:%M"), inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="remind", description="Programme un rappel pour tout le monde")
@app_commands.describe(
    duration="Durée (ex: 5m, 2h, 1d)",
    message="Message du rappel"
)
async def remind_all(interaction: discord.Interaction, duration: str, message: str):
    # Vérifier les permissions (admin ou manage messages)
    if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_messages):
        await interaction.response.send_message("❌ **Vous devez être administrateur pour créer des rappels publics !**", ephemeral=True)
        return
    
    seconds = parse_duration(duration)
    
    if not seconds:
        await interaction.response.send_message("❌ **Format de durée invalide !** Utilisez: `5m`, `2h`, `1d`", ephemeral=True)
        return
    
    if seconds > 86400 * 7:  # Max 7 jours
        await interaction.response.send_message("❌ **Durée maximale: 7 jours !**", ephemeral=True)
        return
    
    # Créer un ID unique pour le rappel
    reminder_id = f"public_{interaction.guild.id}_{datetime.now().timestamp()}"
    
    # Créer le timer
    timer_task = asyncio.create_task(send_reminder(
        interaction.user.id, 
        interaction.channel.id, 
        f"@everyone {message}", 
        reminder_id
    ))
    
    REMINDER_TIMERS[reminder_id] = {
        'task': timer_task,
        'delay': seconds,
        'user_id': interaction.user.id,
        'message': message
    }
    
    # Calculer l'heure du rappel
    remind_time = datetime.now() + timedelta(seconds=seconds)
    
    embed = discord.Embed(
        title="📢 Rappel public programmé",
        description=f"**Message:** {message}",
        color=0xe74c3c
    )
    embed.add_field(name="⏱️ Dans", value=format_duration(seconds), inline=True)
    embed.add_field(name="📅 Le", value=remind_time.strftime("%d/%m/%Y à %H:%M"), inline=True)
    embed.set_footer(text=f"Créé par {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)


# ==================== IMAGES ALÉATOIRES ====================

async def get_random_image(api_url, image_type):
    """Récupère une image aléatoire depuis une API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    return None
    except Exception as e:
        print(f"Erreur API {image_type}: {e}")
        return None

@bot.tree.command(name="meme", description="Affiche un mème aléatoire")
async def random_meme(interaction: discord.Interaction):
    await interaction.response.defer()
    
    data = await get_random_image("https://meme-api.com/gimme", "meme")
    
    if not data or 'url' not in data:
        await interaction.followup.send("❌ **Impossible de récupérer un mème !**")
        return
    
    embed = discord.Embed(
        title=f"😂 {data.get('title', 'Mème aléatoire')}",
        color=0x9b59b6,
        timestamp=discord.utils.utcnow()
    )
    
    embed.set_image(url=data['url'])
    embed.set_footer(text=f"Source: r/{data.get('subreddit', 'memes')} • Upvotes: {data.get('ups', 'N/A')}")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="chaton", description="Affiche un chat mignon")
async def random_cat(interaction: discord.Interaction):
    await interaction.response.defer()
    
    data = await get_random_image("https://api.thecatapi.com/v1/images/search", "chat")
    
    if not data or len(data) == 0:
        await interaction.followup.send("❌ **Impossible de récupérer un chat !**")
        return
    
    cat_data = data[0]
    
    embed = discord.Embed(
        title="🐱 Chat mignon",
        color=0xe67e22,
        timestamp=discord.utils.utcnow()
    )
    
    embed.set_image(url=cat_data['url'])
    embed.set_footer(text="Source: TheCatAPI")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="chien", description="Affiche un chien mignon")
async def random_dog(interaction: discord.Interaction):
    await interaction.response.defer()
    
    data = await get_random_image("https://api.thedogapi.com/v1/images/search", "chien")
    
    if not data or len(data) == 0:
        await interaction.followup.send("❌ **Impossible de récupérer un chien !**")
        return
    
    dog_data = data[0]
    
    embed = discord.Embed(
        title="🐶 Chien mignon",
        color=0x8e44ad,
        timestamp=discord.utils.utcnow()
    )
    
    embed.set_image(url=dog_data['url'])
    embed.set_footer(text="Source: TheDogAPI")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="fox", description="Affiche un renard mignon")
async def random_fox(interaction: discord.Interaction):
    await interaction.response.defer()
    
    data = await get_random_image("https://randomfox.ca/floof/", "renard")
    
    if not data or 'image' not in data:
        await interaction.followup.send("❌ **Impossible de récupérer un renard !**")
        return
    
    embed = discord.Embed(
        title="🦊 Renard mignon",
        color=0xd35400,
        timestamp=discord.utils.utcnow()
    )
    
    embed.set_image(url=data['image'])
    embed.set_footer(text="Source: RandomFox")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="quote", description="Affiche une citation inspirante")
async def random_quote(interaction: discord.Interaction):
    await interaction.response.defer()
    
    data = await get_random_image("https://zenquotes.io/api/random", "citation")
    
    if not data or len(data) == 0:
        await interaction.followup.send("❌ **Impossible de récupérer une citation !**")
        return
    
    quote_data = data[0]
    
    embed = discord.Embed(
        title="💭 Citation du jour",
        description=f"*\"{quote_data.get('q', 'Citation non disponible')}\"*",
        color=0x1abc9c,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="Auteur", value=f"— {quote_data.get('a', 'Anonyme')}", inline=False)
    embed.set_footer(text="Source: ZenQuotes")
    
    await interaction.followup.send(embed=embed)


# ==================== BLAGUES FRANÇAISES ====================

async def get_blague_api(category="random", joke_id=None):
    """Récupère une blague depuis Blagues API"""
    try:
        if not BLAGUES_API_TOKEN:
            return None
            
        headers = {
            "Authorization": f"Bearer {BLAGUES_API_TOKEN}",
            "User-Agent": "KomradeBot/2.0"
        }
        
        if joke_id:
            url = f"https://www.blagues-api.fr/api/id/{joke_id}"
        elif category == "random":
            url = "https://www.blagues-api.fr/api/random"
        else:
            url = f"https://www.blagues-api.fr/api/type/{category}/random"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Erreur Blagues API: {response.status}")
                    return None
    except Exception as e:
        print(f"Erreur Blagues API: {e}")
        return None

@bot.tree.command(name="blague", description="Affiche une blague française")
@app_commands.describe(categorie="Type de blague")
@app_commands.choices(categorie=[
    app_commands.Choice(name="🎲 Aléatoire", value="random"),
    app_commands.Choice(name="💻 Développeur", value="dev"),
    app_commands.Choice(name="🌚 Humour noir", value="dark"),
    app_commands.Choice(name="🔞 Limites", value="limit"),
    app_commands.Choice(name="🍺 Beauf", value="beauf"),
    app_commands.Choice(name="👱‍♀️ Blondes", value="blondes")
])
async def blague_command(interaction: discord.Interaction, categorie: app_commands.Choice[str]):
    await interaction.response.defer()
    
    if not BLAGUES_API_TOKEN:
        embed = discord.Embed(
            title="🔐 Token manquant",
            description="**La clé API Blagues n'est pas configurée !**\n\nAjoutez `BLAGUES_API_TOKEN=votre_token` dans le fichier `.env`",
            color=0xe74c3c
        )
        embed.add_field(name="📝 Comment obtenir un token", value="1. Allez sur https://www.blagues-api.fr/\n2. Créez un compte\n3. Récupérez votre token", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    blague_data = await get_blague_api(categorie.value)
    
    if not blague_data:
        await interaction.followup.send("❌ **Impossible de récupérer une blague !**")
        return
    
    # Emojis par catégorie
    category_emojis = {
        "dev": "💻",
        "dark": "🌚", 
        "limit": "🔞",
        "beauf": "🍺",
        "blondes": "👱‍♀️",
        "global": "🎭"
    }
    
    category_names = {
        "dev": "Développeur",
        "dark": "Humour noir",
        "limit": "Limites", 
        "beauf": "Beauf",
        "blondes": "Blondes",
        "global": "Générale"
    }
    
    blague_type = blague_data.get("type", "global")
    emoji = category_emojis.get(blague_type, "🎭")
    type_name = category_names.get(blague_type, "Générale")
    
    embed = discord.Embed(
        title=f"{emoji} Blague {type_name}",
        color=0xf39c12,
        timestamp=discord.utils.utcnow()
    )
    
    # Texte de la blague
    joke_text = blague_data.get("joke", "Blague indisponible")
    answer_text = blague_data.get("answer", "")
    
    if answer_text:
        embed.add_field(name="😂 Blague", value=joke_text, inline=False)
        embed.add_field(name="💡 Chute", value=answer_text, inline=False)
    else:
        embed.description = f"**{joke_text}**"
    
    embed.set_footer(
        text=f"Blague #{blague_data.get('id', 'N/A')} • Source: Blagues-API.fr",
        icon_url="https://www.blagues-api.fr/favicon.ico"
    )
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="blagueinfo", description="Statistiques de Blagues API")
async def blague_info(interaction: discord.Interaction):
    await interaction.response.defer()
    
    if not BLAGUES_API_TOKEN:
        embed = discord.Embed(
            title="🔐 Token manquant",
            description="**La clé API Blagues n'est pas configurée !**",
            color=0xe74c3c
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    try:
        headers = {
            "Authorization": f"Bearer {BLAGUES_API_TOKEN}",
            "User-Agent": "KomradeBot/2.0"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.blagues-api.fr/api/count", headers=headers, timeout=10) as response:
                if response.status == 200:
                    count_data = await response.json()
                    total_blagues = count_data.get("count", "N/A")
                else:
                    total_blagues = "N/A"
    except:
        total_blagues = "N/A"
    
    embed = discord.Embed(
        title="📊 Blagues API - Statistiques",
        color=0x3498db,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="📚 Total blagues", value=f"`{total_blagues}`", inline=True)
    embed.add_field(name="🇫🇷 Langue", value="`Français`", inline=True)
    embed.add_field(name="🆓 Gratuit", value="`Oui`", inline=True)
    
    categories = """
    💻 **Développeur** - Blagues geek
    🌚 **Humour noir** - Pour les âmes fortes
    🔞 **Limites** - Attention, c'est osé !
    🍺 **Beauf** - Humour de comptoir
    👱‍♀️ **Blondes** - Classiques
    🎲 **Aléatoire** - Toutes catégories
    """
    
    embed.add_field(name="📂 Catégories", value=categories, inline=False)
    
    embed.set_footer(text="Source: Blagues-API.fr • API française communautaire")
    embed.set_thumbnail(url="https://www.blagues-api.fr/favicon.ico")
    
    await interaction.followup.send(embed=embed, ephemeral=True)


# ==================== COMMANDES STATS & XP ====================

@bot.tree.command(name="level", description="Affiche votre niveau et XP")
async def level_command(interaction: discord.Interaction, utilisateur: discord.User = None):
    target_user = utilisateur or interaction.user
    
    # Logger l'utilisation de la commande
    log_command_usage(interaction.user.id, "level", interaction.guild.id if interaction.guild else "DM")
    
    user_data = get_user_xp(target_user.id)
    
    # Calcul XP pour le prochain niveau
    current_level = user_data["level"]
    current_xp = user_data["xp"]
    
    # Calcul XP nécessaire pour le niveau actuel et suivant
    xp_for_current_level = 0
    xp_needed = 100
    for level in range(1, current_level):
        xp_for_current_level += xp_needed
        xp_needed += 50
    
    xp_for_next_level = xp_for_current_level + xp_needed
    xp_progress = current_xp - xp_for_current_level
    xp_remaining = xp_for_next_level - current_xp
    
    # Barre de progression
    progress_bar_length = 20
    progress = min(xp_progress / xp_needed, 1.0)
    filled_bars = int(progress * progress_bar_length)
    progress_bar = "█" * filled_bars + "░" * (progress_bar_length - filled_bars)
    
    embed = discord.Embed(
        title=f"📊 Niveau de {target_user.display_name}",
        color=0x00ff88,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="🏆 Niveau", value=f"`{current_level}`", inline=True)
    embed.add_field(name="✨ XP Total", value=f"`{current_xp:,}`", inline=True)
    embed.add_field(name="💬 Messages", value=f"`{user_data['messages']:,}`", inline=True)
    
    embed.add_field(
        name="📈 Progression",
        value=f"`{progress_bar}`\n`{xp_progress}/{xp_needed} XP` ({progress*100:.1f}%)",
        inline=False
    )
    
    embed.add_field(name="🎯 Prochain niveau", value=f"`{xp_remaining:,} XP restants`", inline=True)
    
    embed.set_thumbnail(url=target_user.avatar.url if target_user.avatar else None)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Classement des niveaux")
async def leaderboard_command(interaction: discord.Interaction):
    # Logger l'utilisation de la commande
    log_command_usage(interaction.user.id, "leaderboard", interaction.guild.id if interaction.guild else "DM")
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id, username, level, xp, messages_count 
            FROM users 
            ORDER BY level DESC, xp DESC 
            LIMIT 10
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            await interaction.response.send_message("📊 **Aucune donnée de niveau disponible !**")
            return
        
        embed = discord.Embed(
            title="🏆 Classement des Niveaux",
            color=0xffd700,
            timestamp=discord.utils.utcnow()
        )
        
        leaderboard_text = ""
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        
        for i, (user_id, username, level, xp, messages) in enumerate(results):
            medal = medals[i]
            leaderboard_text += f"{medal} **{username}** - Niv.`{level}` (`{xp:,}` XP, `{messages:,}` msg)\n"
        
        embed.description = leaderboard_text
        
        embed.set_footer(text="Classement basé sur le niveau puis l'XP total")
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        print(f"Erreur leaderboard: {e}")
        await interaction.response.send_message("❌ **Erreur lors de la récupération du classement !**")

@bot.tree.command(name="stats", description="Statistiques du serveur")
async def stats_command(interaction: discord.Interaction):
    # Logger l'utilisation de la commande
    log_command_usage(interaction.user.id, "stats", interaction.guild.id if interaction.guild else "DM")
    
    await interaction.response.defer()
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        guild_id = str(interaction.guild.id) if interaction.guild else "DM"
        
        # Stats générales
        cursor.execute("SELECT COUNT(*) FROM messages WHERE guild_id = ?", (guild_id,))
        total_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM messages WHERE guild_id = ?", (guild_id,))
        active_users = cursor.fetchone()[0]
        
        # Top 5 utilisateurs les plus actifs
        cursor.execute("""
            SELECT u.username, COUNT(m.id) as msg_count
            FROM users u
            JOIN messages m ON u.user_id = m.user_id
            WHERE m.guild_id = ?
            GROUP BY u.user_id, u.username
            ORDER BY msg_count DESC
            LIMIT 5
        """, (guild_id,))
        top_users = cursor.fetchall()
        
        # Heures les plus actives
        cursor.execute("""
            SELECT hour, COUNT(*) as count
            FROM messages
            WHERE guild_id = ?
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 3
        """, (guild_id,))
        peak_hours = cursor.fetchall()
        
        # Jours de la semaine les plus actifs
        cursor.execute("""
            SELECT day_of_week, COUNT(*) as count
            FROM messages
            WHERE guild_id = ?
            GROUP BY day_of_week
            ORDER BY count DESC
            LIMIT 3
        """, (guild_id,))
        peak_days = cursor.fetchall()
        
        conn.close()
        
        embed = discord.Embed(
            title="📈 Statistiques du Serveur",
            color=0x3498db,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="💬 Messages totaux", value=f"`{total_messages:,}`", inline=True)
        embed.add_field(name="👥 Utilisateurs actifs", value=f"`{active_users:,}`", inline=True)
        embed.add_field(name="📊 Moyenne/user", value=f"`{total_messages//max(active_users,1):,}`", inline=True)
        
        # Top utilisateurs
        if top_users:
            top_text = "\n".join([f"`{i+1}.` **{name}** - `{count:,}` msg" for i, (name, count) in enumerate(top_users)])
            embed.add_field(name="🏆 Top Utilisateurs", value=top_text, inline=False)
        
        # Heures de pointe
        if peak_hours:
            days_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
            hours_text = " • ".join([f"`{hour}h ({count:,})`" for hour, count in peak_hours])
            embed.add_field(name="🕐 Heures de pointe", value=hours_text, inline=False)
            
            if peak_days:
                days_text = " • ".join([f"`{days_fr[day]} ({count:,})`" for day, count in peak_days])
                embed.add_field(name="📅 Jours actifs", value=days_text, inline=False)
        
        embed.set_footer(text="Statistiques basées sur l'activité enregistrée")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Erreur stats: {e}")
        await interaction.followup.send("❌ **Erreur lors de la récupération des statistiques !**")


# ==================== MENU HELP ====================

@bot.tree.command(name="help", description="Affiche l'aide et toutes les commandes disponibles")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 KomradeBot - Guide des Commandes",
        description="**Voici toutes les commandes disponibles !**",
        color=0x00ff88,
        timestamp=discord.utils.utcnow()
    )
    
    # Musique
    music_commands = """
    🎵 `/play [url/recherche]` - Joue de la musique YouTube
    ⏸️ `/pause` - Met en pause la musique
    ▶️ `/resume` - Reprend la musique
    ⏭️ `/skip` - Passe à la chanson suivante
    ⏹️ `/stop` - Arrête la musique (déco auto 5min)
    👋 `/leave` - Déconnecte le bot immédiatement
    📋 `/queue` - Affiche la file d'attente
    """
    
    # Divertissement
    fun_commands = """
    😂 `/meme` - Mème aléatoire depuis Reddit
    🐱 `/chaton` - Photo de chat mignon
    🐶 `/chien` - Photo de chien mignon
    🦊 `/fox` - Photo de renard mignon
    💭 `/quote` - Citation inspirante
    ✂️ `/pfc [choix]` - Pierre-Feuille-Ciseaux
    🎭 `/blague [catégorie]` - Blague française (6 types)
    📊 `/blagueinfo` - Stats de l'API blagues
    """
    
    # Utilitaires
    utility_commands = """
    💰 `/btc` - Prix du Bitcoin en temps réel
    💎 `/eth` - Prix d'Ethereum en temps réel
    🌤️ `/weather [ville]` - Météo d'une ville
    📊 `/poll [question] [options]` - Sondage personnalisé
    ✅ `/quickpoll [question]` - Sondage Oui/Non rapide
    """
    
    # Rappels
    reminder_commands = """
    ⏰ `/remindme [durée] [message]` - Rappel personnel
    📢 `/remind [durée] [message]` - Rappel public (admin)
    📝 *Formats: 5m, 2h, 1d (max 7 jours)*
    """
    
    # Stats et XP
    stats_commands = """
    📊 `/level [utilisateur]` - Affiche niveau et XP
    🏆 `/leaderboard` - Classement des niveaux
    📈 `/stats` - Statistiques du serveur
    📊 *+15-50 XP par message (cooldown 60s)*
    """
    
    embed.add_field(name="🎵 **MUSIQUE**", value=music_commands, inline=False)
    embed.add_field(name="🎮 **DIVERTISSEMENT**", value=fun_commands, inline=False)
    embed.add_field(name="🔧 **UTILITAIRES**", value=utility_commands, inline=False)
    embed.add_field(name="⏰ **RAPPELS**", value=reminder_commands, inline=False)
    embed.add_field(name="📊 **STATS & XP**", value=stats_commands, inline=False)
    
    # Informations supplémentaires
    embed.add_field(
        name="ℹ️ **INFORMATIONS**",
        value="""
        🔗 **Auto-déconnexion:** 5 minutes d'inactivité musicale
        🎯 **Total commandes:** 27+ disponibles
        ⚡ **APIs utilisées:** YouTube, CoinGecko, OpenWeather, Blagues-API, etc.
        🛠️ **Support:** Slash commands uniquement
        🗄️ **Base de données:** SQLite pour stats/XP
        """,
        inline=False
    )
    
    embed.set_footer(
        text="KomradeBot v2.0 • Développé avec ❤️ en Python",
        icon_url=bot.user.avatar.url if bot.user.avatar else None
    )
    
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="info", description="Informations sur le bot")
async def bot_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📊 Informations du Bot",
        color=0x3498db,
        timestamp=discord.utils.utcnow()
    )
    
    # Statistiques du bot
    total_guilds = len(bot.guilds)
    total_users = len(set(bot.get_all_members()))
    
    embed.add_field(name="🏠 Serveurs", value=f"`{total_guilds}`", inline=True)
    embed.add_field(name="👥 Utilisateurs", value=f"`{total_users}`", inline=True)
    embed.add_field(name="📶 Ping", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    
    embed.add_field(name="🐍 Python", value=f"`3.11+`", inline=True)
    embed.add_field(name="📚 Discord.py", value=f"`2.5.2`", inline=True)
    embed.add_field(name="🎵 FFmpeg", value=f"`Installé`", inline=True)
    
    # Statut des APIs
    embed.add_field(
        name="🔌 **APIs Connectées**",
        value="""
        ✅ YouTube (yt-dlp)
        ✅ CoinGecko (crypto)
        ✅ OpenWeather (météo)
        ✅ Reddit (mèmes)
        ✅ TheCatAPI / TheDogAPI
        ✅ Blagues-API (blagues FR)
        """,
        inline=False
    )
    
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Point d'entrée de l'application
bot.run(TOKEN)
