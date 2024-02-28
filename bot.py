from typing import Final
import os
import time
import random2 as random
from dotenv import load_dotenv
from discord import Intents, Client, Message
from responses import get_response

# Token
load_dotenv()
TOKEN: Final[str] = os.getenv('TOKEN')

# Bot setup
intents: Intents = Intents.default()
intents.message_content = True
client: Client = Client(intents=intents)

# Cooldown for the roulette command
roulette_cooldown = {}
COOLDOWN_TIME: Final[int] = 5

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

# Handle messages
@client.event
async def on_message(message: Message) -> None:
    if message.author == client.user:
        return

    # Message infos
    username: str = str(message.author)
    user_message: str = message.content

    # If the bot is pinged it answers
    if client.user.mentioned_in(message):
        await message.channel.send('Coucou ' + username + ' je suis KomradeBot :)')

    if user_message.startswith('$roulette'):
        # Cooldown
        if username in roulette_cooldown and time.time() - roulette_cooldown[username] < COOLDOWN_TIME:
            await message.channel.send(f'Cooldown ! Tu dois attendre {COOLDOWN_TIME - int(time.time() - roulette_cooldown[username])} secondes...')
            return

        # Update the user's cooldown
        roulette_cooldown[username] = time.time()

        if random.randint(0, 5) == 0:
            await message.channel.send('HES DED')
            if message.author.voice and message.author.voice.channel:
                await message.author.move_to(None)
        else:
            await message.channel.send('OK')

# Handle new members
@client.event
async def on_member_join(member):
    await member.guild.system_channel.send(f'Bienvenue {member.name}!')

# Entry point
def main() -> None:
    client.run(token=TOKEN)

if __name__ == '__main__':
    main()
