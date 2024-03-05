import os
import time
from typing import Final
import random2 as random
from discord import Client, Intents
from discord.ext import commands

from dotenv import load_dotenv

from music_cog import music_cog

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

# Insultes
with open('insultes.txt', 'r', encoding='utf-8') as f:
    insults = [line.strip() for line in f]

# Remove the built-in help command
client.remove_command("help")

# Starting bot
@client.event
async def on_ready() -> None:
    await client.add_cog(music_cog(client))
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
    await ctx.channel.send(f"```Liste des commandes disponibles:\n{commands_list}```")

@client.command(name='ano', description='Envoie un message anonyme (ex: $ano message)')
async def echo_delete(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

@client.command(name='insult', description='Insulte un membre du serveur (ex: $insult @user)')
async def insult(ctx, *, message):
    # Get the identified user in the message
    if len(ctx.message.mentions) > 0:
        # Delete the message that triggered the command
        await ctx.message.delete()
        await ctx.send(random.choice(insults) + " " + ctx.message.mentions[0].mention)
    else:
        await ctx.send("Tu dois mentionner un membre du serveur")

# Entry point
def main() -> None:
    client.run(token=TOKEN)

if __name__ == '__main__':
    main()
