import os
import time
from typing import Final, List, Dict, Any, Optional, Union
import random2 as random
import random
from discord import Client, Intents, FFmpegPCMAudio, VoiceClient
from discord.ext import commands
import discord
import asyncio
from yt_dlp import YoutubeDL

from dotenv import load_dotenv

# Chargement des variables d'environnement
_ = load_dotenv()
# Token du bot Discord
TOKEN: Final[str] = os.getenv("TOKEN") or ""

# Configuration du bot avec les intents requis
intents: Intents = Intents.default()
intents.message_content = True  # Permet au bot de lire le contenu des messages
intents.members = True  # Permet au bot de suivre les membres du serveur
client: Client = commands.Bot(command_prefix="$", intents=intents)

# Pas besoin de suivi de cooldown pour les commandes musicales

# Supprime la commande d'aide intégrée pour utiliser notre commande personnalisée
_ = client.remove_command("help")


# Variables pour les fonctionnalités musicales
is_playing = False
is_paused = False
is_skipping = False
music_queue = []
YDL_OPTIONS = {"format": "bestaudio", "noplaylist": "False"}
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
vc = None


# Événement d'initialisation du bot
@client.event
async def on_ready() -> None:
    print(f"{client.user} connecté")


# Commandes musicales définies ci-dessous


# Commande d'aide - affiche toutes les commandes disponibles
@client.command(name="help", description="Affiche la liste des commandes")
async def help_command(ctx: commands.Context) -> None:
    """Affiche la liste des commandes disponibles avec leurs descriptions"""

    # Dictionnaire pour organiser les commandes par catégorie
    categories = {"Musique": [], "Utilitaires": []}

    # Dictionnaire pour traduire les descriptions en français
    translations = {
        "Play music from YouTube": "Joue de la musique depuis YouTube",
        "Play a specific song from the queue (ex: $play_song 3)": "Joue une chanson spécifique de la file d'attente (ex: $play_song 3)",
        "Pause the music": "Met en pause la musique",
        "Resume the music": "Reprend la lecture de la musique",
        "Skip to the next song": "Passe à la chanson suivante",
        "Show the music queue": "Affiche la file d'attente",
        "Stop the music and clear the queue": "Arrête la musique et vide la file d'attente",
        "Leave the voice channel": "Quitte le canal vocal",
        "Displays the list of commands": "Affiche la liste des commandes",
    }

    # Trier les commandes par catégorie
    for command in client.commands:
        translated_desc = translations.get(command.description, command.description)

        if command.name in ["help"]:
            categories["Utilitaires"].append((command.name, translated_desc))
        else:
            categories["Musique"].append((command.name, translated_desc))

        # Formater le message d'aide
    help_message = "**📋 LISTE DES COMMANDES DISPONIBLES**\n\n"

    for category, cmds in categories.items():
        if cmds:
            help_message += f"**__{category}__**\n"
            for name, desc in cmds:
                # Ajouter les alias si disponibles
                aliases = ""
                cmd = client.get_command(name)
                if cmd and cmd.aliases:
                    aliases = f" (alias: {', '.join(cmd.aliases)})"

                help_message += f"• **${name}**{aliases}\n  {desc}\n"

            help_message += "\n"

    await ctx.channel.send(help_message)


# Fonctionnalités musicales
def search_yt(item):
    """Rechercher une chanson ou une playlist sur YouTube"""
    with YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(item, download=False)
            if "_type" in info and info["_type"] == "playlist":
                songs = []
                for song in info["entries"]:
                    try:
                        songs.append({"source": song["url"], "title": song["title"]})
                    except Exception:
                        continue
                # Shuffle the songs
                random.shuffle(songs)
                return songs
            else:
                return {"source": info["url"], "title": info["title"]}
        except Exception:
            return None


def play_next():
    """Jouer la chanson suivante dans la file d'attente"""
    global is_playing, is_skipping, music_queue, vc

    if len(music_queue) > 0 and vc and vc.is_connected():
        is_playing = True

        m_url = music_queue[0][0]["source"]
        m_title = music_queue[0][0]["title"]

        music_queue.pop(0)

        if not is_skipping:
            if not vc.is_playing():
                vc.play(
                    discord.FFmpegPCMAudio(m_url, **FFMPEG_OPTIONS),
                    after=lambda e: play_next() if not is_skipping else None,
                )
                ctx = music_queue[0][2]
                client.loop.create_task(
                    send_playing_message(m_title, ctx)
                )  # Send a message to the channel
        else:
            client.loop.create_task(wait_and_play_next())

    else:
        is_playing = False
        client.loop.create_task(wait_and_disconnect())


async def send_playing_message(title, ctx):
    """Envoie un message indiquant la chanson en cours de lecture"""
    await ctx.send(f"🎵 **En cours de lecture:** {title}")


async def wait_and_disconnect():
    """Attendre 2 minutes d'inactivité avant de se déconnecter"""
    global vc, is_playing
    await asyncio.sleep(120)
    if not is_playing:
        await vc.disconnect()
        vc = None


async def wait_and_play_next():
    """Attendre brièvement puis jouer la chanson suivante"""
    global is_skipping
    await asyncio.sleep(1)
    is_skipping = False
    play_next()


async def play_music(ctx, pop_first=True):
    """Commencer à jouer de la musique à partir de la file d'attente"""
    global is_playing, music_queue, vc

    try:
        if vc is not None and vc.is_connected():
            await vc.disconnect()
        vc = await music_queue[0][1].channel.connect()
    except Exception as e:
        print(f"An error occurred while connecting to the voice channel: {e}")
        return

    if len(music_queue) > 0:
        is_playing = True
        m_url = music_queue[0][0]["source"]
        m_title = music_queue[0][0]["title"]

        if vc == None or not vc.is_connected():
            vc = await music_queue[0][1].channel.connect()

            if vc == None:
                await ctx.send("❌ **Je n'ai pas pu me connecter au canal vocal.**")
                return
        else:
            await vc.move_to(music_queue[0][1].channel)

        if pop_first:
            music_queue.pop(0)

        vc.play(
            discord.FFmpegPCMAudio(m_url, **FFMPEG_OPTIONS), after=lambda e: play_next()
        )
        await send_playing_message(m_title, ctx)
    else:
        is_playing = False


# Commandes musicales
@client.command(
    name="play_song",
    description="Joue une chanson spécifique de la file d'attente (ex: $play_song 3)",
)
async def play_song(ctx: commands.Context, song_number: int) -> None:
    """Joue une chanson spécifique de la file d'attente par son numéro"""
    global music_queue, vc

    print(f"Playing song number {song_number}")
    if len(music_queue) >= song_number > 0:
        song = music_queue.pop(song_number - 1)
        music_queue.insert(0, song)
        if vc != None and vc.is_playing():
            vc.stop()
        await play_music(ctx, pop_first=False)
    else:
        await ctx.send("❌ **Numéro de chanson invalide.**")


@client.command(
    name="play",
    aliases=["p", "playing"],
    description="Joue de la musique depuis YouTube",
)
async def play(ctx: commands.Context, *args) -> None:
    """Joue de la musique depuis une URL YouTube ou une recherche"""
    global is_paused, is_playing, music_queue

    query = " ".join(args)

    if ctx.author.voice is None:
        await ctx.send(
            "🔊 **Vous devez être dans un canal vocal pour jouer de la musique.**"
        )
    elif is_paused:
        vc.resume()
    else:
        songs = search_yt(query)
        if songs is None:
            await ctx.send("❌ **La musique n'est pas disponible.**")
        else:
            if isinstance(songs, list):
                for song in songs:
                    if isinstance(song, dict):
                        music_queue.append([song, ctx.author.voice, ctx])
                await ctx.send("✅ **Chansons ajoutées à la file d'attente**")
            elif isinstance(songs, dict):
                music_queue.append([songs, ctx.author.voice, ctx])
                await ctx.send("✅ **Chanson ajoutée à la file d'attente**")
            if is_playing == False:
                await play_music(ctx)


@client.command(name="pause", description="Met en pause la musique")
async def pause(ctx: commands.Context, *args) -> None:
    """Met en pause ou reprend la lecture de la musique en cours"""
    global is_playing, is_paused, vc

    if vc and vc.is_playing():
        is_playing = False
        is_paused = True
        vc.pause()
    elif is_paused:
        is_playing = True
        is_paused = False
        vc.resume()


@client.command(
    name="resume", aliases=["r"], description="Reprend la lecture de la musique"
)
async def resume(ctx: commands.Context, *args) -> None:
    """Reprend la lecture de la musique en pause"""
    global is_playing, is_paused, vc

    if is_paused:
        is_playing = True
        is_paused = False
        vc.resume()


@client.command(name="skip", aliases=["s"], description="Passe à la chanson suivante")
async def skip(ctx: commands.Context, *args) -> None:
    """Passe la chanson en cours de lecture"""
    global is_skipping, vc

    if vc != None and vc.is_playing():
        is_skipping = True
        vc.stop()
        client.loop.create_task(wait_and_play_next())
    else:
        await ctx.send("❌ **Je ne suis pas en train de jouer de la musique.**")


@client.command(name="queue", aliases=["q"], description="Affiche la file d'attente")
async def queue(ctx: commands.Context) -> None:
    """Affiche la file d'attente actuelle"""
    global music_queue

    if len(music_queue) > 0:
        for i in range(0, len(music_queue), 10):
            retval = "**🎶 FILE D'ATTENTE**\n\n"
            for j in range(i, min(i + 10, len(music_queue))):
                retval += f"**{j + 1}.** {music_queue[j][0]['title']}\n"
            await ctx.send(retval)
    else:
        await ctx.send("📭 **La file d'attente est vide.**")


@client.command(
    name="clear",
    aliases=["c", "bin"],
    description="Arrête la musique et vide la file d'attente",
)
async def clear(ctx: commands.Context, *args) -> None:
    """Arrête la musique et vide la file d'attente"""
    global is_playing, music_queue, vc

    if vc != None and is_playing:
        vc.stop()
    music_queue = []
    await ctx.send("🗑️ **La file d'attente a été vidée.**")


@client.command(
    name="leave",
    aliases=["l", "disconnect", "d"],
    description="Quitte le canal vocal",
)
async def leave(ctx: commands.Context) -> None:
    """Déconnecte le bot du canal vocal"""
    global is_playing, is_paused, vc

    is_playing = False
    is_paused = False
    if vc and vc.is_connected():
        await vc.disconnect()


# Gestion des commandes inconnues
@client.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    """Gère les erreurs de commande, notamment les commandes inconnues"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(
            "❓ **Commande inconnue.** Utilisez `$help` pour voir la liste des commandes disponibles."
        )
    else:
        raise error


# Point d'entrée de l'application
def main() -> None:
    """Démarre le bot Discord avec le token configuré"""
    client.run(token=TOKEN)


if __name__ == "__main__":
    main()
