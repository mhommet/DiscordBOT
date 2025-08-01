#!/usr/bin/env python3
"""Test script pour vérifier la connectivité vocale Discord sur WSL"""

import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class TestBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents, heartbeat_timeout=60.0)

    async def on_ready(self):
        print(f'Bot connecté: {self.user}')
        print('Test de connexion vocale...')
        
        # Trouve le premier canal vocal disponible
        for guild in self.guilds:
            for channel in guild.voice_channels:
                try:
                    print(f'Tentative de connexion à {channel.name}...')
                    voice_client = await channel.connect(timeout=30.0, reconnect=False)
                    print('✅ Connexion vocale réussie!')
                    await asyncio.sleep(3)
                    await voice_client.disconnect()
                    print('✅ Déconnexion réussie!')
                    await self.close()
                    return
                except Exception as e:
                    print(f'❌ Erreur: {e}')
        
        print('❌ Aucun canal vocal trouvé')
        await self.close()

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Token manquant dans .env")
        exit(1)
    
    client = TestBot()
    client.run(TOKEN)