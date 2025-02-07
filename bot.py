#large playlist timeout and queue not autoplaying next
import os
import discord
from discord.ext import commands
import yt_dlp
import asyncio
import logging
import time
import re
#pynacl library is required sometimes for !play to work

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

#create client with intents and command prefix
client = commands.Bot(command_prefix="!", intents=intents)

class DiscordLogHandler(logging.Handler):
    def __init__(self, bot, channel_id):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id

    async def send_log(self, log_entry):
        await self.bot.wait_until_ready()  # Ensure the bot is fully connected
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            await channel.send(f"```{log_entry}```")

    def emit(self, record):
        log_entry = self.format(record)
        # Use asyncio.create_task to schedule the coroutine
        asyncio.create_task(self.send_log(log_entry))

class YTDLPLogger:
    def __init__(self, bot, log_channel_id, delay=5):
        self.bot = bot
        self.log_channel_id = log_channel_id
        self.bot_channel_id = 1047368874758242334
        self.delay = delay  # Interval in seconds to send logs
        self.download_delay = 1 #interval in sec to send download progress
        self.log_buffer = []  # Buffer to accumulate logs
        self.last_sent_time = time.time()  # Track last sent time
        self.last_sent_download_time = time.time()
        self.lock = asyncio.Lock()
        self.download_lock = asyncio.Lock()
        self.download_buffer = ""
        self.downloading_message = None #store the downloading message for editing

    #send logs and clear buffer
    """async def send_logs(self):
        if self.log_buffer:
            logs = "\n".join(self.log_buffer)
            channel = self.bot.get_channel(self.log_channel_id)
            if channel:
                await channel.send(logs)
            self.log_buffer.clear()"""

    async def send_progress(self):
        if self.download_buffer:
            progress = self.download_buffer
            channel = self.bot.get_channel(self.bot_channel_id)
                
            if channel:
                #if the first progress message hasnt been sent
                if self.downloading_message is None:
                    self.downloading_message = await channel.send(progress)
                #edit the already sent progress message
                else:
                    await self.downloading_message.edit(content=progress)

            self.download_buffer = ""

    #send logs every 5 seconds
    """async def cont_timer(self):
        while True and self.log_buffer:
            await asyncio.sleep(self.delay)
            await self.send_logs()"""

    """async def download_cont_timer(self):
        while True and self.download_buffer:
            await asyncio.sleep(self.download_delay)
            await self.send_progress()"""

    #add log to buffer and start timer
    """async def add_log(self, msg):
        self.log_buffer.append(msg)

        #lock to prevent race condition
        async with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_sent_time

            if elapsed >= self.delay:
                await self.cont_timer()
                self.last_sent_time = current_time  #reset the last sent time"""

    #add progress to download buffer and start timer
    async def add_progress(self, msg):
        async with self.download_lock:
            current_time = time.time()
            elapsed = current_time - self.last_sent_download_time

            if elapsed >= self.download_delay:
                self.download_buffer = msg
                await self.send_progress() 
                self.last_sent_download_time = current_time  

    def debug(self, msg):
        """asyncio.create_task(self.add_log(f"``` LOG: {msg}```"))"""
        print(msg)

    def warning(self, msg):
        """asyncio.create_task(self.add_log(f"``` WARNING: {msg}```"))"""
        print(msg)

    def error(self, msg):
        """asyncio.create_task(self.add_log(f"``` ERROR: {msg}```"))"""
        print(msg)

    def my_hook(self, d):
        asyncio.create_task(self._my_hook(d))  # Create a task to call the async method

    def remove_ansi_escape_sequences(self, text):
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[mK]')
        return ansi_escape.sub('', text)

    #function to send progress updates
    async def _my_hook(self, d):
        """if d['status'] == 'downloading':
            msg = f"Downloading: {d['_percent_str']} at {d['_speed_str']} ETA: {d['_eta_str']}"
            print(msg)
            msg = self.remove_ansi_escape_sequences(msg)  #remove any ANSI escape sequences
            await self.add_progress(f"``` PROGRESS: {msg}```")
                
        elif d['status'] == 'finished':
            msg = f"Download complete: {d['filename']}"
            print(msg)
            msg = self.remove_ansi_escape_sequences(msg)  #remove any ANSI escape sequences
            await self.add_progress(f"``` PROGRESS: {msg}```")"""

FFMPEG_OPTIONS = {
    'options': '-vn -b:a 192k -ar 48000'  # Set audio bitrate to 192 kbps and sample rate to 48 kHz
}

log_channel_id = 1316373392143810610
logger = YTDLPLogger(client, 1316373392143810610)

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'quiet': False,
    'extractaudio': True,  # Only extract audio
    'audioformat': 'mp3',  # Optional: You can specify 'mp3' or 'opus'
    'audioquality': '192K',  # Audio quality
    'logger': YTDLPLogger(client, log_channel_id),  # Use the custom logger
    'progress_hooks': [logger.my_hook]
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

async def main():
    #initialize the bot and custom logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()
    discord_handler = DiscordLogHandler(client, channel_id=1316373392143810610)
    discord_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(discord_handler)

    await client.add_cog(MusicBot(client))
    await client.start('token')

asyncio.run(main())
