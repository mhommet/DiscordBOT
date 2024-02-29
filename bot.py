from typing import Final
import os
import time
import random2 as random
from dotenv import load_dotenv
from discord import Intents, Client, Message
import discord
import asyncio
from responses import get_response
from discord.ext import commands, tasks
import yt_dlp as youtube_dl

# Token
load_dotenv()
TOKEN: Final[str] = os.getenv('TOKEN')

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
with open('citations.txt', 'r', encoding='utf-8') as f:
    quotes = [line.strip() for line in f]

# Remove the built-in help command
client.remove_command("help")

# Message event
async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        print('Message is empty')
        return

    if is_private := user_message[0] == '?':
        user_message = user_message[1:]

    try:
        response: str = get_response(user_message)
        await message.author.send(response) if is_private else message.channel.send(response)
    except Exception as e:
        print('Error:', e)

# Starting bot
@client.event
async def on_ready() -> None:
    print(f'{client.user} connected')

# Define commands with names and descriptions
@client.command(name="roulette", description="Roulette russe (5s de cooldown)")
async def roulette(ctx):
    if ctx.author.name in roulette_cooldown and time.time() - roulette_cooldown[ctx.author.name] < COOLDOWN_TIME:
        await ctx.channel.send(f'Cooldown ! Tu dois attendre {COOLDOWN_TIME - int(time.time() - roulette_cooldown[ctx.author.name])} secondes...')
        return

    if random.randint(0, 5) == 0:
        await ctx.channel.send('HES DED')
        if ctx.author.voice and ctx.author.voice.channel:
            await ctx.author.move_to(None)
    else:
        await ctx.channel.send('OK').then()
        roulette_cooldown[ctx.author.name] = time.time()

@client.command(name="magic", description="Tour de magie... (1h de cooldown)")
async def magic(ctx):
    global magic_last_used
    if time.time() - magic_last_used < MAGIC_COOLDOWN_TIME:
        await ctx.channel.send(f'Cooldown ! Tu dois attendre {MAGIC_COOLDOWN_TIME - int(time.time() - magic_last_used)} secondes...')
        return

    

    # Kick a random member from the voice channel
    if ctx.author.voice and ctx.author.voice.channel:
        members = ctx.author.voice.channel.members
        if members:
            member_to_kick = random.choice(members)
            await member_to_kick.move_to(None)
            await ctx.channel.send(f'Et pouf ! {member_to_kick.name} a disparu !')
            magic_last_used = time.time()
    else: 
        await ctx.channel.send('Tu dois être dans un salon vocal pour utiliser /magic')    

@client.command(name="k2a", description="Envoie une citation de Kaaris")
async def quote(ctx):
    await ctx.send(random.choice(quotes))

# Help command
@client.command(name="help", description="Affiche la liste des commandes")
async def help(ctx):
    commands_list = "\n".join([f"- {command.name}: {command.description}" for command in client.commands])
    await ctx.channel.send(f'Liste des commandes disponibles:\n{commands_list}')

# Music

youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}
ffmpeg_options = {
    'options': '-vn'
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = ""
    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        fileName = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(fileName, **ffmpeg_options), data=data), data['title']
    
async def join(ctx):
    if not ctx.message.author.voice:
        return
    else:
        channel = ctx.message.author.voice.channel
    await channel.connect()
    
@client.command(name='leave', description='Leaves the voice channel')
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send("The bot is not connected to a voice channel.")

@client.command(name='play', description='Joue de la musique depuis une url youtube')
async def play(ctx,url):
    await join(ctx)
    try :
        server = ctx.message.guild
        voice_channel = server.voice_client
        async with ctx.typing():
            try :
                player, title = await YTDLSource.from_url(url, loop=client.loop)
                async def delete_file(error):
                    try:
                        await discord.VoiceClient.cleanup(voice_channel)
                        os.remove(player.source.original)
                        await leave(ctx)
                    except Exception as e:
                        print("Error while deleting file: ", e)
                try:
                    voice_channel.play(player, after=delete_file)
                except Exception as e:
                    delete_file(None)
                    raise e
                await ctx.send('**Lecture en cours:** {}'.format(title))
            except Exception as e:
                await ctx.send('Une erreur est survenue: {}'.format(str(e)))
    except:
        await ctx.send("Je ne suis pas dans un channel vocal.")

@client.command(name='pause', description='Met en pause la musique')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        await voice_client.pause()
    else:
        await ctx.send("Je ne suis pas en train de jouer de la musique.")
    
@client.command(name='resume', description='Remet en route la musique')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        await voice_client.resume()
    else:
        await ctx.send("Je ne joue pas de musique. Utilise la commande play")
        
@client.command(name='stop', description='Arrête la musique')
async def stop(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        await discord.VoiceClient.cleanup(voice_client)
        os.remove(voice_client.source.original)
        await leave(ctx)
    else:
        await ctx.send("Je ne suis pas en train de jouer de la musique.")

# Entry point
def main() -> None:
    client.run(token=TOKEN)

if __name__ == '__main__':
    main()
