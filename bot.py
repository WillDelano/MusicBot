#large playlist timeout and queue not autoplaying next
import os
import discord
from discord.ext import commands
import yt_dlp
import asyncio
#pynacl library is required sometimes for !play to work

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

FFMPEG_OPTIONS = {
    'options': '-vn -b:a 192k -ar 48000'  # Set audio bitrate to 192 kbps and sample rate to 48 kHz
}

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'quiet': False,
    'extractaudio': True,  # Only extract audio
    'audioformat': 'mp3',  # Optional: You can specify 'mp3' or 'opus'
    'audioquality': '192K'  # Audio quality
}

class MusicBot(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.current_path = None
        self.pause = False
        self.current_song = {
            "title" : None,
            "url" : None,
            "duration" : None,
            "channel" : None,
            "views" : None
        }

    #plays a song via yt search
    @commands.command()
    async def play(self, ctx, *, search):
        if ctx.channel.name != "bot":
            await self.wrong_channel(ctx)
            return
            
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None
        if not voice_channel: return await ctx.send("You must be in a voice channel.")

        if not ctx.voice_client:
            await voice_channel.connect()

        async with ctx.typing():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                song = {
                "title" : None,
                "url" : None,
                "duration" : None,
                "channel" : None,
                "views" : None
                }

                if "list=" in search and "v=" not in search:
                    try:
                        print(f"Playlist URL detected: {search}")

                        await ctx.send("Playlist link detected. Please wait while each song is downloaded from youtube (this can take about 3 seconds per song or 4.5 minutes per 100).")
                        info = ydl.extract_info(search, download=True)

                        # Check if the entries exist in the info object
                        if 'entries' in info:
                            print(f"Found {len(info['entries'])} entries in the playlist.")

                            #add playlist songs to queue
                            for entry in info['entries']: 
                                file_path = ydl.prepare_filename(entry)
                                
                                #populate song data
                                song = {
                                    "title": entry.get("title"),
                                    "url": entry.get("webpage_url"),
                                    "duration": entry.get("duration"),
                                    "channel": entry.get("channel"),
                                    "views": entry.get("view_count"),
                                }

                                self.queue.append((file_path, song))
                                print(f"Added to queue: {song['title']}")

                        else:
                            print("No entries found in playlist.")
                    except Exception as e:
                        print(f"Error extracting playlist: {str(e)}")
                        await ctx.send(f"Error processing the playlist: {str(e)}")

                else:
                    if 'https://' in search:
                        info = ydl.extract_info(search, download=True)
                    else:
                        info = ydl.extract_info(f"ytsearch:{search}", download=True)

                    if 'entries' in info:
                        info = info['entries'][0]
                    
                    file_path = ydl.prepare_filename(info)

                    song = {
                        "title": info.get("title"),
                        "url": info.get("webpage_url"),
                        "duration": info.get("duration"),
                        "channel": info.get("channel"),
                        "views": info.get("view_count"),
                    }

                    self.queue.append((file_path, song))

        if ctx.voice_client.is_playing() or self.pause:
            await ctx.send(f"Added to queue: **{song['title']}**")
        if not ctx.voice_client.is_playing() and not self.pause:
            await self.play_next(ctx)


    #deletes the files after playing
    def cleanup(self, ctx, file_path):
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")


    #plays the next song in queue
    async def play_next(self, ctx):
        if self.queue:

            #pop top of queue
            path, self.current_song = self.queue.pop(0)
        
            await ctx.send(f"Now playing: **{self.current_song['title']}**")

            #play song
            source = discord.FFmpegOpusAudio(path, **FFMPEG_OPTIONS)
            ctx.voice_client.play(source, after=lambda e: self.cleanup(ctx, path))
            self.current_path = path

            while ctx.voice_client.is_playing() or self.pause:
                await asyncio.sleep(1)
            
            if self.queue:
                await self.play_next(ctx)

        else:
            await ctx.send("Queue is empty")


    #skips currently playing song
    @commands.command()
    async def skip(self, ctx):
        if ctx.channel.name != "bot":
            await self.wrong_channel(ctx)
            return
        
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Skipped.")
            self.cleanup(ctx, self.current_path)

        if len(self.queue) > 0:
            await self.play_next(ctx)


    #prints the queue
    @commands.command()
    async def queue(self, ctx):
        if ctx.channel.name != "bot":
            await self.wrong_channel(ctx)
            return
        
        if len(self.queue) < 1:
            await ctx.send("Queue is empty.")
        else:
            q = []
            for pair in self.queue:
                q.append(pair[1]['title'])
            
            message = "\n".join(q)

            await ctx.send(f"Queue:\n**{message}**")


    #pause current song
    @commands.command()        
    async def pause(self, ctx):
        if ctx.channel.name != "bot":
            await self.wrong_channel(ctx)
            return
        
        if ctx.voice_client and ctx.voice_client.is_playing():
            self.pause = True
            ctx.voice_client.pause()
            await ctx.send("Paused the current song.")


    #resume song after pausing
    @commands.command()        
    async def resume(self, ctx):
        if ctx.channel.name != "bot":
            await self.wrong_channel(ctx)
            return
        
        if ctx.voice_client and not ctx.voice_client.is_playing():
            ctx.voice_client.resume()
            self.pause = False
            await ctx.send("Resumed the current song.")


    #stops playback
    @commands.command()        
    async def stop(self, ctx):
        if ctx.channel.name != "bot":
            await self.wrong_channel(ctx)
            return
        
        if ctx.voice_client:
            ctx.voice_client.stop()

            #delete all remaining downloaded songs
            for song in self.queue:
                self.cleanup(ctx, song[0])

            self.queue.clear()
            await ctx.send("Stopped all playback and cleared queue.")
        await ctx.voice_client.disconnect()


    #current song stats
    @commands.command()
    async def current(self, ctx):
        if ctx.channel.name != "bot":
            await self.wrong_channel(ctx)
            return

        if not ctx.voice_client or not ctx.voice_client.is_playing:
            await ctx.send("There is no song currently playing.")
        else:
            #set to hours and min
            durationMin = self.current_song['duration'] // 60
            durationSec = self.current_song['duration'] % 60

            #add commas
            views = self.current_song['views']
            views = f"{views:,}"

            await ctx.send(f"**Current song:** **{self.current_song['title']}** uploaded by **{self.current_song['channel']}**\n**Link:** {self.current_song['url']}\n**Duration:** {durationMin}:{durationSec}\t**Views:** {views}")


    #show all commands
    @commands.command()
    async def commands(self, ctx):
        if ctx.channel.name != "bot":
            await self.wrong_channel(ctx)
            return

        help_message = """
        **🎶 EJ's Commands 🎶**

    **Current issues:** Playlists over ~30 songs don't play

        - **!play [song/playlist name or URL]**: Plays a song or adds it to the queue if one is playing. If you provide a YouTube playlist URL, it will queue up all songs in the playlist.

        - **!skip**: Skips the currently playing song and plays the next song in the queue. If there are no more songs in the queue, playback will stop.

        - **!queue**: Displays the current song queue. Shows all songs that are queued up and ready to play next.

        - **!pause**: Pauses the currently playing song. Use this if you want to temporarily stop the music without clearing the queue.

        - **!resume**: Resumes the currently paused song. If the music is paused, use this to continue playing it.

        - **!stop**: Stops the current playback and clears the queue. This also disconnects the bot from the voice channel.

        - **!current**: Shows information about the currently playing song. Displays details like title, duration, views, and more.

    ---

    *Enjoy using and abusing EJ (2)!  😈*
        """
        await ctx.send(help_message)


    #send wrong channel message
    async def wrong_channel(self, ctx):
        await ctx.reply("Wrong channel. Now EJ's going to touch me. Thanks.")


#create client with intents and command prefix
client = commands.Bot(command_prefix="!", intents=intents)

async def main():
    await client.add_cog(MusicBot(client))
    await client.start('MTAxNDYzNzI2NjY1Nzg3Mzk4Mg.GObs5T.lhPOAqQbL8mpfYBWqgdQLxqtmRY0_UZZ3hzje')

asyncio.run(main())
