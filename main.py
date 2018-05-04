import configparser
import logging
import os
import sys
import urllib.request

import discord
import praw

config = configparser.ConfigParser()
config.read('config.ini')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)


class DiscordRedditSyncClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.bg_task = self.loop.create_task(self.job())

    async def job(self):
        await self.wait_until_ready()
        logger.info('connected to discord: @' + self.user.name + "#" + self.user.discriminator)

        redditClient = praw.Reddit(client_id=config['REDDIT']['CLIENT_ID'],
                                   client_secret=config['REDDIT']['CLIENT_SECRET'],
                                   user_agent=config['REDDIT']['USER_AGENT'],
                                   password=config['REDDIT']['PASSWORD'],
                                   username=config['REDDIT']['USERNAME'])
        logger.info('connected to reddit')

        # subreddit
        subreddit = redditClient.subreddit(config['REDDIT']['SUBREDDIT'])
        logger.info('found ' + str(sum(1 for x in subreddit.emoji)) + " emojis for r/" + subreddit.display_name)

        # get emojis from guild
        guild = self.get_guild(int(config['DISCORD']['GUILD_ID']))
        logger.info('found ' + str(len(guild.emojis)) + " emojis for " + guild.name)

        for emoji in guild.emojis:
            filename = emoji.name
            exists = False
            for redditEmoji in subreddit.emoji:
                if redditEmoji.name == emoji.name:
                    exists = True
                    break
            if exists:
                logger.info('skipping ' + emoji.name + ' because it already exists on reddit')
                continue

            if emoji.animated:
                logger.info('skipping ' + emoji.name + ' because it is animated')
                continue
            if emoji.url.endswith('.png'):
                filename += '.png'
            if emoji.url.endswith('.jpg'):
                filename += '.jpg'

            logger.info('downloading ' + emoji.url + ' to ' + filename)
            request = urllib.request.Request(emoji.url, headers={'User-Agent': config['DISCORD']['USER_AGENT']})
            with urllib.request.urlopen(request) as response, open(
                    filename, 'wb') as out_file:
                data = response.read()
                out_file.write(data)

            if os.stat(filename).st_size > 64000:
                os.remove(filename)
                logger.info('skipping ' + emoji.name + ' because it is too big')
                continue

            logger.info('uploading ' + emoji.name)
            subreddit.emoji.add(emoji.name, filename)

            os.remove(filename)

        await self.logout()


if __name__ == '__main__':
    client = DiscordRedditSyncClient()
    client.run(config['DISCORD']['TOKEN'])
