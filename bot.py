import os
import time
from typing import Final
import random2 as random
from discord import Client, Intents
from discord.ext import commands
from openai import OpenAI
from gtts import gTTS
import discord
from pydub import AudioSegment
import asyncio

from dotenv import load_dotenv

from music_cog import music_cog

# Token
load_dotenv()
TOKEN: Final[str] = os.getenv("TOKEN")

# OpenAI setup
OPENAI_API_KEY: Final[str] = os.getenv("OPENAI_API_KEY")

openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Bot setup
intents: Intents = Intents.default()
intents.message_content = True
intents.members = True
client: Client = commands.Bot(command_prefix="$", intents=intents)

# Cooldowns
# Roulette
roulette_cooldown = {}
COOLDOWN_TIME: Final[int] = 5
# Magic
magic_last_used = 0
MAGIC_COOLDOWN_TIME: Final[int] = 3600

# Quotes
with open("citations.txt", "r", encoding="utf-8") as f:
    quotes = [line.strip() for line in f]

# Insultes
with open("insultes.txt", "r", encoding="utf-8") as f:
    insults = [line.strip() for line in f]

# Remove the built-in help command
client.remove_command("help")


# Starting bot
@client.event
async def on_ready() -> None:
    await client.add_cog(music_cog(client))
    print(f"{client.user} connected")


# Define commands with names and descriptions
@client.command(name="roulette", description="Roulette russe (5s de cooldown)")
async def roulette(ctx):
    if (
        ctx.author.name in roulette_cooldown
        and time.time() - roulette_cooldown[ctx.author.name] < COOLDOWN_TIME
    ):
        await ctx.channel.send(
            f"Cooldown ! Tu dois attendre {COOLDOWN_TIME - int(time.time() - roulette_cooldown[ctx.author.name])} secondes..."
        )
        return

    if random.randint(0, 5) == 0:
        await ctx.channel.send("HES DED")
        if ctx.author.voice and ctx.author.voice.channel:
            await ctx.author.move_to(None)
    else:
        await ctx.channel.send("OK").then()
        roulette_cooldown[ctx.author.name] = time.time()


@client.command(name="magic", description="Tour de magie... (1h de cooldown)")
async def magic(ctx):
    global magic_last_used
    if time.time() - magic_last_used < MAGIC_COOLDOWN_TIME:
        await ctx.channel.send(
            f"Cooldown ! Tu dois attendre {MAGIC_COOLDOWN_TIME - int(time.time() - magic_last_used)} secondes..."
        )
        return

    # Kick a random member from the voice channel
    if ctx.author.voice and ctx.author.voice.channel:
        members = ctx.author.voice.channel.members
        if members:
            member_to_kick = random.choice(members)
            await member_to_kick.move_to(None)
            await ctx.channel.send(f"Et pouf ! {member_to_kick.name} a disparu !")
            magic_last_used = time.time()
    else:
        # If the user is not in channel we send a message
        await ctx.channel.send("Tu dois être dans un salon vocal pour utiliser /magic")


@client.command(name="k2a", description="Envoie une citation de Kaaris")
async def quote(ctx):
    await ctx.send(random.choice(quotes))


# Help command
@client.command(name="help", description="Affiche la liste des commandes")
async def help(ctx):
    commands_list = "\n".join(
        [f"- {command.name}: {command.description}" for command in client.commands]
    )
    await ctx.channel.send(f"```Liste des commandes disponibles:\n{commands_list}```")


@client.command(name="ano", description="Envoie un message anonyme (ex: $ano message)")
async def echo_delete(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)


@client.command(
    name="insult", description="Insulte un membre du serveur (ex: $insult @user)"
)
async def insult(ctx, *, message):
    # Get the identified user in the message
    if len(ctx.message.mentions) > 0:
        # Delete the message that triggered the command
        await ctx.message.delete()
        await ctx.send(random.choice(insults) + " " + ctx.message.mentions[0].mention)
    else:
        await ctx.send("Tu dois mentionner un membre du serveur")


# OpenAI request
@client.command(name="chat", description="Pose moi une question")
async def chat(ctx, *, message):
    # Check if the user in a voice channel
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("Tu dois être dans un salon vocal pour utiliser cette commande.")
        return

    # Check if there is an openai client
    if openai_client is None:
        await ctx.send(
            "Pour utiliser cette commande tu dois mettre ton token d'api OpenAI dans le fichier .env sous la clé OPENAI_API_KEY."
        )
        return

    # Send a message to say that the bot is thinking
    await ctx.send("Je réfléchis...")

    chat_completion = openai_client.chat.completions.create(
        messages=[{"role": "system", "content": message}],
        model="gpt-3.5-turbo",
    )

    # Convert the response to speech
    tts = gTTS(text=chat_completion.choices[0].message.content, lang="fr")
    tts.save("response.mp3")

    audio = AudioSegment.from_mp3("response.mp3")

    # Increase the speed of the audio
    audio = audio.speedup(playback_speed=1.2)
    audio.export("response.ogg", format="ogg")

    # Join the voice channel
    voice_channel = ctx.author.voice.channel
    voice_client = discord.utils.get(client.voice_clients, guild=ctx.guild)

    if voice_client and voice_client.is_connected():
        await voice_client.move_to(voice_channel)
    else:
        voice_client = await voice_channel.connect()

    # Play the response
    voice_client.play(
        discord.FFmpegPCMAudio(executable="ffmpeg", source="response.ogg"),
        after=lambda e: delete_audio_files(),
    )

    await leave_channel_if_afk(voice_client)


def delete_audio_files():
    # Deleting the temporary audio files
    os.remove("response.mp3")
    os.remove("response.ogg")


async def leave_channel_if_afk(voice_client):
    await asyncio.sleep(120)  # Wait for 2 minutes before leaving the channel
    if not voice_client.is_playing():
        await voice_client.disconnect()


# Handling unknown commands
@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(
            "Je ne connais pas cette commande. Utilise $help pour voir la liste des commandes disponibles."
        )
    else:
        raise error


# Entry point
def main() -> None:
    client.run(token=TOKEN)


if __name__ == "__main__":
    main()
