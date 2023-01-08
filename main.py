import os
import re
import csv
import aiohttp
import asyncio
import youtube_dl
import time
import discord
from discord.ext import commands

openai_key = os.environ['OPENAI_KEY']
discord_token = os.environ['DISCORD_TOKEN']

youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None
)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


async def write_reply(content):
    with open('log.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(content)


async def write_log(content):
    with open('error.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(content)


async def add_period(text):
    if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text[-1]) != None:
        text = text + '。'
    elif re.search(r'[a-zA-Z]', text[-1]) != None:
        text = text + '.'
    else:
        text = text + '.'
    return text


async def check_param(prompt):
    model = re.search(r'model=([0-9a-zA-Z\-]+)', prompt)
    max_tokens = re.search(r'max_tokens=(\d+)', prompt)
    temperature = re.search(r'temperature=(\d+(?:\.\d+)?)', prompt)
    top_p = re.search(r'top_p=(\d+(?:\.\d+)?)', prompt)

    if model != None:
        model = model.group(1)
        prompt = prompt.replace(f'model={model}', '')
    else:
        model = 'text-davinci-003'
    if max_tokens != None:
        max_tokens = max_tokens.group(1)
        prompt = prompt.replace(f'max_tokens={max_tokens}', '')
    else:
        max_tokens = 512
    if temperature != None:
        temperature = temperature.group(1)
        prompt = prompt.replace(f'temperature={temperature}', '')
    else:
        temperature = 0.9
    if top_p != None:
        top_p = top_p.group(1)
        prompt = prompt.replace(f'top_p={top_p}', '')
    else:
        top_p = 1

    print(
        f'model: {model}, max_tokens: {max_tokens}, temperature: {temperature}, top_p: {top_p}')

    return [prompt, model, max_tokens, temperature, top_p]


async def is_valid_model(model):
    models = await get_models()
    if models == None:
        return False
    if model in models:
        return True
    else:
        return False


async def is_url(text):
    url = re.search(
        r'^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$', text)
    if url != None:
        return True
    else:
        return False


async def get_models():
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://api.openai.com/v1/models',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {}'.format(openai_key),
            }
        ) as response:
            if response.status == 200:
                data = await response.json()
                models = []
                for model in data['data']:
                    models.append(model['id'])
                return models
            else:
                print('Error: ' + str(response.status))
                return None


async def get_answer(prompt, model, max_tokens, temperature, top_p):
    reply = await openai(prompt, model, max_tokens, temperature, top_p)
    return reply


async def openai(prompt, model, max_tokens, temperature, top_p):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://api.openai.com/v1/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {}'.format(openai_key),
            },
            json={
                'model': str(model),
                'prompt': str(prompt),
                'max_tokens': int(max_tokens),
                'temperature': float(temperature),
                'top_p': float(top_p),
                'n': 1,
            }
        ) as response:
            print('Response_status: ' + str(response.status))
            if response.status == 200:
                data = await response.json()
                reply = [
                    data['created'],
                    data['model'],
                    prompt,
                    data['choices'][0]['text'],
                    data['choices'][0]['finish_reason'],
                    data['usage']['prompt_tokens'],
                    data['usage']['completion_tokens'],
                    data['usage']['total_tokens']
                ]
                print('Reply: ' + reply[3])
                return reply
            else:
                print('Error: ' + str(response.status))
                return None


async def get_image(prompt):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://api.openai.com/v1/images/generations',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {}'.format(openai_key),
            },
            json={
                'prompt': str(prompt),
                'n': 1,
                'size': '256x256'
            }
        ) as response:
            if response.status == 200:
                data = await response.json()
                reply = [
                    data['created'],
                    'image',
                    prompt,
                    data['data'][0]['url']
                ]
                print('Reply: ' + reply[1])
                return reply
            else:
                print('Error: ' + str(response.status))
                return None


async def is_flagged(text):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://api.openai.com/v1/moderations',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {}'.format(openai_key),
            },
            json={
                'input': str(text),
                'model': 'text-moderation-latest'
            }
        ) as response:
            if response.status == 200:
                data = await response.json()
                reply = [
                    time.time(),
                    'moderation',
                    text,
                    data['results'][0]['flagged']
                ]
                for category in data['results'][0]['categories']:
                    reply.append(category)
                    reply.append(data['results'][0]['categories'][category])
                    reply.append(data['results'][0]
                                 ['category_scores'][category])
                print('Flagged: ' + str(reply[3]))
                if reply[3] == True:
                    await write_log(reply)
                return reply[3]
            else:
                print('Error: ' + str(response.status))
                return None


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print(discord.__version__)
    print('------')
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(
            name=f'AI'
        )
    )
    print('Ready!')


@bot.event
async def on_command_error(ctx, error):
    try:
        await ctx.message.remove_reaction('👀', bot.user)
        await ctx.message.add_reaction('❌')
        await ctx.send(f'Error: {str(error)}')
    except:
        await ctx.send(f'Error: {ctx.author}, {str(error)}')

@bot.command()
async def join(ctx):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return
    await ctx.author.voice.channel.connect()

@bot.command()
async def play(ctx, *, url):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

    await ctx.send(f'Now playing: {player.title}')

@bot.command()
async def volume(ctx, volume: int):
    if ctx.voice_client is None:
        return await ctx.send("Not connected to a voice channel.")

    ctx.voice_client.source.volume = volume / 100
    await ctx.send(f"Changed volume to {volume}%")

@bot.command()
async def stop(ctx):
    await ctx.voice_client.disconnect()

@bot.command()
async def ai(ctx, *, prompt):
    await ctx.message.add_reaction('👀')
    print('Prompt: ' + prompt)
    modified = False

    if re.match(r'model=([0-9a-zA-Z\-]+)|max_tokens=(\d+)|temperature=(\d+(?:\.\d+)?)|top_p=(\d+(?:\.\d+)?)', prompt):
        if ctx.author.id == 226674196112080896:
            params = await check_param(prompt)
            prompt = params[0]
            model = params[1]
            max_tokens = params[2]
            temperature = params[3]
            top_p = params[4]
            modified = True
        else:
            await ctx.reply('Error: You do not have permission to use parameters')
            await ctx.message.add_reaction('❌')
            await ctx.message.remove_reaction('👀', bot.user)
            return
    else:
        model = 'text-davinci-003'
        max_tokens = 512
        temperature = 0.9
        top_p = 1

    if not prompt.endswith(('。', '．', '.', '、', '，', ',', '！', '？', '!', '?', '︙', '︰', '…', '‥')):
        prompt = await add_period(prompt)
        modified = True

    prompt = prompt.strip()

    if modified:
        print('Modified Prompt: ' + prompt)

    if len(prompt) >= 128:
        await ctx.reply('Error: Prompt too long({} characters)'.format(len(prompt)))
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return

    if not await is_valid_model(model):
        await ctx.reply('Error: Invalid model')
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return

    if await is_url(prompt):
        await ctx.reply('Error: Prompt is URL')
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return

    flag = await is_flagged(prompt)
    if flag == True:
        await ctx.reply('Error: Prompt has been marked as violated\nYour prompt has been reported and recorded.')
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return
    elif flag == None:
        await ctx.reply('Error: Failed to check prompt')
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return

    async with ctx.typing():
        reply = await get_answer(prompt, model, max_tokens, temperature, top_p)
        if reply != None:
            try:
                await ctx.reply(reply[3])
                await ctx.message.add_reaction('✅')
                await ctx.message.remove_reaction('👀', bot.user)
            except:
                await ctx.send(ctx.author.mention + reply[3])
        else:
            await ctx.message.add_reaction('❌')
            await ctx.message.remove_reaction('👀', bot.user)
            return

    await write_reply(reply)


@bot.command()
async def img(ctx, *, prompt):
    await ctx.message.add_reaction('👀')
    print('Prompt: ' + prompt)

    prompt = prompt.strip()

    if ctx.author.id != 226674196112080896:
        await ctx.reply('Error: You do not have permission to use parameters')
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return

    if len(prompt) >= 1000:
        await ctx.reply('Error: Prompt too long({} characters)'.format(len(prompt)))
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return

    if await is_url(prompt):
        await ctx.reply('Error: Prompt is URL')
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return

    flag = await is_flagged(prompt)
    if flag == True:
        await ctx.reply('Error: Prompt has been marked as violated\nYour prompt has been reported and recorded.')
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return
    elif flag == None:
        await ctx.reply('Error: Failed to check prompt')
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return

    async with ctx.typing():
        reply = await get_image(prompt)
        if reply != None:
            try:
                embed = discord.Embed(
                    title='Image generation', description='{}'.format(reply[2]), color=0x00ff00)
                embed.set_image(url='{}'.format(reply[3]))
                embed.set_footer(text='OpenAI')
                await ctx.reply(embed=embed)
                await ctx.message.add_reaction('✅')
                await ctx.message.remove_reaction('👀', bot.user)
            except:
                embed = discord.Embed(
                    title='Image generation', description='{}'.format(reply[2]), color=0x00ff00)
                embed.set_image(url='{}'.format(reply[3]))
                embed.set_footer(text='OpenAI')
                await ctx.send(ctx.author.mention)
                await ctx.send(embed=embed)
        else:
            await ctx.message.add_reaction('❌')
            await ctx.message.remove_reaction('👀', bot.user)
            return

    await write_reply(reply)


@bot.command()
async def help(ctx):
    await ctx.message.add_reaction('👀')
    embed = discord.Embed(
        title='Help', description='snakeの研究用Botです。頻繁にアップデートが入り機能が大幅に変更されます。\n自宅のラズパイが死ななければ24時間稼働します。\n維持コストはタダじゃないので、使いすぎないようにしてくれると嬉しいです。\n蛇の財布次第で機能が制限されます。', color=0x00ff00)
    embed.add_field(
        name='!ai', value='Generates text. Usage: `!ai [prompt]`', inline=False)
    embed.add_field(
        name='!img', value='Generates an image. Usage: `!img [prompt]` Devs only.', inline=False)
    embed.add_field(name='!ping', value='Pong!', inline=False)
    embed.add_field(
        name='!invite', value='Invite the bot to your server!', inline=False)
    embed.add_field(name='!help', value='Shows this message.', inline=False)
    embed.add_field(name='!version',
                    value='Shows the bot\'s version.', inline=False)
    embed.add_field(name='!join', value='Join the voice channel.', inline=False)
    embed.add_field(name='!play', value='Play YouTube video. Usage: `!play [YouTube URL]`', inline=False)
    embed.add_field(name='!stop', value='Stop playing music.', inline=False)
    embed.add_field(name='!volume', value='Change the volume. Usage: `!volume [0-100]`', inline=False)
    embed.set_footer(
        text='Made by snake#0232',
        icon_url='https://cdn.discordapp.com/avatars/226674196112080896/8032fdc281918376bf55a35d8e67b24a.png'
    )
    await ctx.send(embed=embed)
    await ctx.message.add_reaction('✅')
    await ctx.message.remove_reaction('👀', bot.user)


@bot.command()
async def ping(ctx):
    await ctx.message.add_reaction('👀')
    await ctx.send('Pong! {0}ms'.format(round(bot.latency * 1000, 1)))
    await ctx.message.add_reaction('✅')
    await ctx.message.remove_reaction('👀', bot.user)


@bot.command()
async def invite(ctx):
    await ctx.message.add_reaction('👀')
    await ctx.send('Private bot, sorry!')
    await ctx.message.add_reaction('✅')
    await ctx.message.remove_reaction('👀', bot.user)


@bot.command()
async def version(ctx):
    await ctx.message.add_reaction('👀')
    await ctx.send('Version: 1.0.0')
    await ctx.message.add_reaction('✅')
    await ctx.message.remove_reaction('👀', bot.user)


# chat = Chat(email=chatgpt_email, password=chatgpt_password)
bot.run(discord_token)
