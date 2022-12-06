import os
import re
import csv
import aiohttp
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None
)


async def write_csv(content):
    with open('log.csv', 'a', newline='') as f:
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


async def get_answer(prompt, model='text-davinci-003', max_tokens=512, temperature=0.9, top_p=1, n=1):


async def is_valid_model(model):
    models = await get_models()
    if model in models:
        return True
    else:
        return False


async def get_models():
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://api.openai.com/v1/models',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {openai_key}',
            }
        ) as response:
            if response.status == 200:
                data = await response.json()
                models = []
                for model in data['data']['id']:
                    models.append(model)
                return models
            else:
                print('Error: ' + str(response.status))
                return None


    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://api.openai.com/v1/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']
            },
            json={
                'model': model,
                'prompt': prompt,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'top_p': top_p,
                'n': n
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
        await ctx.message.add_reaction('❌')
        await ctx.send(f'Error: ぬるぽ({str(error)}')
    except:
        await ctx.send(f'Error: ぬるぽ({ctx.author}, {str(error)})')


@bot.command()
async def ai(ctx, *, prompt):
    await ctx.message.add_reaction('👀')
    print('Prompt: ' + prompt)

    if len(prompt) >= 128:
        await ctx.reply('Error: 128文字以上だよ({len(prompt)}文字)')
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return

    if not prompt.endswith(('。', '．', '.', '․', '․', '、', '，', ',', '！', '？', '!', '?', '︙', '︰', '…', '‥')):
        prompt = await add_period(prompt)
        print('Modified Prompt: ' + prompt)

    async with ctx.typing():
        reply = await get_answer(prompt)
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

    await write_csv(reply)


@bot.command()
async def help(ctx):
    await ctx.message.add_reaction('👀')
    embed = discord.Embed(
        title='Help',
        description='そんなもんはねえよ',
        color=0x00ff00
    )
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
    await ctx.send('まだ無いよ')
    await ctx.message.add_reaction('✅')
    await ctx.message.remove_reaction('👀', bot.user)


@bot.command()
async def version(ctx):
    await ctx.message.add_reaction('👀')
    await ctx.send('???')
    await ctx.message.add_reaction('✅')
    await ctx.message.remove_reaction('👀', bot.user)

bot.run(os.environ['DISCORD_BOT_TOKEN'])
