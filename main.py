import os
import re
import csv
import aiohttp
import discord
from discord.ext import commands

openai_key = os.environ['OPENAI_KEY']
discord_token = os.environ['DISCORD_TOKEN']

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


async def check_param(prompt):
    model = re.search(r'model=(\w+)', prompt)
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


async def get_answer(prompt, model, max_tokens, temperature, top_p):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://api.openai.com/v1/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {openai_key}',
            },
            json={
                'model': model,
                'prompt': prompt,
                'max_tokens': 512,  # max_tokens,
                'temperature': temperature,
                'top_p': top_p,
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
        await ctx.send(f'Error: {str(error)}')
    except:
        await ctx.send(f'Error: {ctx.author}, {str(error)}')


@bot.command()
async def ai(ctx, *, prompt):
    await ctx.message.add_reaction('👀')
    print('Prompt: ' + prompt)
    modified = False

    if prompt.search(r'model=(\w+)|max_tokens=(\d+)|temperature=(\d+(?:\.\d+)?)|top_p=(\d+(?:\.\d+)?)') != None:
        params = await check_param(prompt)
        prompt = params[0]
        model = params[1]
        max_tokens = params[2]
        temperature = params[3]
        top_p = params[4]
        modified = True

    if not prompt.endswith(('。', '．', '.', '․', '․', '、', '，', ',', '！', '？', '!', '?', '︙', '︰', '…', '‥')):
        prompt = await add_period(prompt)
        modified = True

    if modified:
        print('Modified Prompt: ' + prompt)

    if len(prompt) >= 128:
        await ctx.reply('Error: Prompt too long({len(prompt)} characters)')
        await ctx.message.add_reaction('❌')
        await ctx.message.remove_reaction('👀', bot.user)
        return

    if not await is_valid_model(model):
        await ctx.reply('Error: Invalid model')
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

    await write_csv(reply)


@bot.command()
async def help(ctx):
    await ctx.message.add_reaction('👀')
    embed = discord.Embed(
        title='Help',
        description='WIP',
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
    await ctx.send('WIP')
    await ctx.message.add_reaction('✅')
    await ctx.message.remove_reaction('👀', bot.user)


@bot.command()
async def version(ctx):
    await ctx.message.add_reaction('👀')
    await ctx.send('WIP')
    await ctx.message.add_reaction('✅')
    await ctx.message.remove_reaction('👀', bot.user)


bot.run(discord_token)
