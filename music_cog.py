import discord
from discord.ext import commands
from yt_dlp import YoutubeDL
import asyncio
import random

class music_cog(commands.Cog):
    def __init__(self, client):
        self.client = client

        self.is_playing = False
        self.is_paused = False
        self.is_skipping = False

        self.music_queue = []
        self.YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist':'False'}
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

        self.vc = None

    def search_yt(self, item):
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(item, download=False)
                if '_type' in info and info['_type'] == 'playlist':
                    songs = []
                    for song in info['entries']:
                        try:
                            songs.append({'source': song['url'], 'title': song['title']})
                        except Exception:
                            continue
                    # Shuffle the songs
                    random.shuffle(songs)
                    return songs
                else:
                    return {'source': info['url'], 'title': info['title']}
            except Exception:
                return None

    def play_next(self):
        if len(self.music_queue) > 0 and self.vc and self.vc.is_connected():
            self.is_playing = True

            m_url = self.music_queue[0][0]['source']
            m_title = self.music_queue[0][0]['title']

            self.music_queue.pop(0)

            if not self.is_skipping:
                if not self.vc.is_playing():
                    self.vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next() if not self.is_skipping else None)
                    ctx = self.music_queue[0][2]
                    self.client.loop.create_task(self.send_playing_message(m_title, ctx))  # Send a message to the channel

            else:
                self.client.loop.create_task(self.wait_and_play_next())
                
        else:
            self.is_playing = False
            self.client.loop.create_task(self.wait_and_disconnect())
       
    async def send_playing_message(self, title, ctx):
        await ctx.send(f"Lecture en cours de : ```{title}```")
         
    async def wait_and_disconnect(self):
        await asyncio.sleep(120)
        if not self.is_playing:
            await self.vc.disconnect()
            self.vc = None
            
    async def wait_and_play_next(self):
        await asyncio.sleep(1)
        self.is_skipping = False
        self.play_next()

    async def play_music(self, ctx, pop_first=True):
        try:
            if self.vc is not None and self.vc.is_connected():
                await self.vc.disconnect()
            self.vc = await self.music_queue[0][1].channel.connect()
        except Exception as e:
            print(f"An error occurred while connecting to the voice channel: {e}")
            return
            
        if len(self.music_queue) > 0:
            self.is_playing = True
            m_url = self.music_queue[0][0]['source']
            m_title = self.music_queue[0][0]['title']

            if self.vc == None or not self.vc.is_connected():
                self.vc = await self.music_queue[0][1].channel.connect()

                if self.vc == None:
                    await ctx.send("Je n'ai pas pu me connecter au channel vocal.")
                    return

            else:
                await self.vc.move_to(self.music_queue[0][1].channel)

            if pop_first:
                self.music_queue.pop(0)

            self.vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next())
            await self.send_playing_message(m_title, ctx)
        else:
            self.is_playing = False

    @commands.command(name="play_song", description="Joue une chanson spécifique de la file d'attente (ex: $play_song 3)")
    async def play_song(self, ctx, song_number: int):
        print(f"Playing song number {song_number}")
        if len(self.music_queue) >= song_number > 0:
            song = self.music_queue.pop(song_number - 1)
            self.music_queue.insert(0, song)
            if self.vc != None and self.vc.is_playing():
                self.vc.stop()
            await self.play_music(ctx, pop_first=False)
        else:
            await ctx.send("Le numéro de la chanson est invalide.")
            
    @commands.command(name="play", aliases=["p", "playing"], description="Joue de la musique depuis Youtube")
    async def play(self, ctx, *args):
        query = " ".join(args)

        if ctx.author.voice is None:
            await ctx.send("Vous devez être dans un channel vocal pour jouer de la musique.")
        elif self.is_paused:
            self.vs.resume()
        else:
            songs = self.search_yt(query)
            if songs is None:
                await ctx.send("La musique n'est pas disponible.")
            else:
                if isinstance(songs, list):
                    for song in songs:
                        if isinstance(song, dict):
                            self.music_queue.append([song, ctx.author.voice, ctx])
                    await ctx.send("Musiques ajoutées à la file d'attente")
                elif isinstance(songs, dict):
                    self.music_queue.append([songs, ctx.author.voice, ctx])
                    await ctx.send("Musique ajoutée à la file d'attente")
                if self.is_playing == False:
                    await self.play_music(ctx)

    @commands.command(name="pause", description="Met en pause la musique")
    async def pause(self, ctx, *args):
        if self.vc.is_playing():
            self.is_playing = False
            self.is_paused = True
            self.vc.pause()
        elif self.is_paused:
            self.is_playing = True
            self.is_paused = False
            self.vc.resume()

    @commands.command(name="resume", aliases=["r"], description="Remet en route la musique")
    async def resume(self, ctx, *args):
        if self.is_paused:
            self.is_playing = True
            self.is_paused = False
            self.vc.resume()

    @commands.command(name="skip", aliases=["s"], description="Passe à la musique suivante")
    async def skip(self, ctx, *args):
        if self.vc != None and self.vc.is_playing():
            self.is_skipping = True
            self.vc.stop()
            self.client.loop.create_task(self.wait_and_play_next())
        else:
            await ctx.send("Je ne suis pas en train de jouer de la musique.")

    @commands.command(name="queue", aliases=["q"], description="Montre la file d'attente")
    async def queue(self, ctx):
        if len(self.music_queue) > 0:
            for i in range(0, len(self.music_queue), 10):
                retval = "```\n"
                for j in range(i, min(i + 10, len(self.music_queue))):
                    retval += f"{j + 1} - {self.music_queue[j][0]['title']}\n"
                retval += "```"
                await ctx.send(retval)
        else:
            await ctx.send("La file d'attente est vide.")

    @commands.command(name="clear", aliases=["c", "bin"], description="Stop la musique et vide la file d'attente")
    async def clear(self, ctx, *args):
        if self.vc != None and self.is_playing:
            self.vc.stop()
        self.music_queue = []
        await ctx.send("La file d'attente a été vidée.")

    @commands.command(name="leave", aliases=["l", "disconnect", "d"], description="Quitte le channel vocal")
    async def leave(self, ctx):
        self.is_playing = False
        self.is_paused = False
        await self.vc.disconnect()
