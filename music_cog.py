import discord
from discord.ext import commands
from yt_dlp import YoutubeDL
import asyncio

class music_cog(commands.Cog):
    def __init__(self, client):
        self.client = client

        self.is_playing = False
        self.is_paused = False

        self.music_queue = []
        self.YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist':'False'}
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

        self.vc = None

    def search_yt(self, item):
        with YoutubeDL(self.YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(item, download=False)
                if '_type' in info and info['_type'] == 'playlist':
                    return [{'source': song['url'], 'title': song['title']} for song in info['entries']]
                else:
                    return {'source': info['url'], 'title': info['title']}
            except Exception:
                return False

    def play_next(self):
        if len(self.music_queue) > 0:
            self.is_playing = True

            m_url = self.music_queue[0][0]['source']

            self.music_queue.pop(0)

            self.vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next())
        else:
            self.is_playing = False
            self.client.loop.create_task(self.wait_and_disconnect())
            
    async def wait_and_disconnect(self):
        await asyncio.sleep(120)
        if not self.is_playing:
            await self.vc.disconnect()
            self.vc = None

    async def play_music(self, ctx):
        if len(self.music_queue) > 0:
            self.is_playing = True
            m_url = self.music_queue[0][0]['source']

            if self.vc == None or not self.vc.is_connected():
                self.vc = await self.music_queue[0][1].channel.connect()

                if self.vc == None:
                    await ctx.send("Je n'ai pas pu me connecter au channel vocal.")
                    return

            else:
                await self.vc.move_to(self.music_queue[0][1])

            self.music_queue.pop(0)

            self.vc.play(discord.FFmpegPCMAudio(m_url, **self.FFMPEG_OPTIONS), after=lambda e: self.play_next())

        else:
            self.is_playing = False

    @commands.command(name="play", aliases=["p", "playing"], description="Joue de la musique depuis Youtube")
    async def play(self, ctx, *args):
        query = " ".join(args)

        if ctx.author.voice is None:
            await ctx.send("Vous devez être dans un channel vocal pour jouer de la musique.")
        elif self.is_paused:
            self.vs.resume()
        else:
            songs = self.search_yt(query)
            if type(songs) == type(True):
                await ctx.send("Je n'ai pas pu trouver la musique. Assurez-vous que l'url de la musique est correcte.")
            else:
                for song in songs:
                    self.music_queue.append([song, ctx.author.voice])
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
        if self.vc != None and self.vc:
            self.vc.stop()
            await self.play_music(ctx)

    @commands.command(name="queue", aliases=["q"], description="Montre la file d'attente")
    async def queue(self, ctx):
        retval = ""

        for i in range(0, len(self.music_queue)):
            if i > 4: break
            retval += self.music_queue[i][0]['title'] + "\n"

        if retval != "":
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
