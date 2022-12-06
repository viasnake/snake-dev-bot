import os
import csv
import aiohttp
import time
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
    symbols = ['。', '．', '.', '․', '․', '、', '，',
               ',', '！', '？', '!', '?', '︙', '︰', '…', '‥']
    if not text.endswith(tuple(symbols)):
        if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text[-1]) != None:
            text = text + '。'
        elif re.search(r'[a-zA-Z]', text[-1]) != None:
            text = text + '.'
        else:
            text = text + '.'
    return text


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


@bot.command()
async def ai(ctx, *, prompt):
    await ctx.message.add_reaction('👀')
    print('Prompt: ' + prompt)
    prompt = await add_period(prompt)
    print('Modified Prompt: ' + prompt)
    async with aiohttp.ClientSession() as session:
        async with ctx.typing():
            async with session.post(
                'https://api.openai.com/v1/completions',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']
                },
                json={
                    'model': 'text-davinci-003',
                    'prompt': prompt,
                    'max_tokens': 512,
                    'temperature': 0.9,
                    'top_p': 1,
                    'n': 1
                }
            ) as response:
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
                    try:
                        await ctx.reply(reply[3])
                        await ctx.message.remove_reaction('👀', bot.user)
                        await ctx.message.add_reaction('✅')
                    except:
                        await ctx.send(
                            '{ctx.author.mention}',
                            '**質問:**',
                            '{reply[2]}',
                            '**回答:**',
                            '{reply[3]}'
                        )
                    print('Reply: ' + reply[3])
                else:
                    reply = 'Error: ' + str(response.status)
                    try:
                        await ctx.reply(reply)
                        await ctx.message.remove_reaction('👀', bot.user)
                        await ctx.message.add_reaction('❌')
                    except:
                        await ctx.send(ctx.author.mention + reply)
                    print('Reply: ' + reply)
    await write_csv(reply)



bot.run(os.environ['DISCORD_BOT_TOKEN'])
