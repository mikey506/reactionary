import logging
from mods.rss import RSSHandler
from mods.info import InfoHandler

class CommandHandler:
    def __init__(self, bot, config):
        self.bot = bot
        self.rss_handler = bot.rss_handler
        self.info_handler = bot.info_handler
        self.channel = config.get('IRC', 'channel')

    def process_command(self, connection, event, message):
        if message.startswith("!parse"):
            self.command_parse(connection, event, message)
        elif message.startswith("!cycle"):
            self.command_cycle(connection)
        elif message.startswith("!feed"):
            self.command_feed(connection, event, message)
        elif message.startswith("!status"):
            self.command_status(connection)
        elif message.startswith("!rehash"):
            self.command_rehash(connection)

    def command_parse(self, connection, event, message):
        try:
            _, url = message.split(maxsplit=1)
            logging.info('Parsing feed once: %s', url)
            self.rss_handler.parse_feed_once(connection, url)
        except ValueError:
            logging.error('Invalid !parse command format')
            connection.privmsg(event.target, "Usage: !parse <feed url>")

    def command_cycle(self, connection):
        self.rss_handler.start_cycle(connection)

    def command_feed(self, connection, event, message):
        try:
            _, url, interval = message.split(maxsplit=2)
            self.rss_handler.update_feed(url, int(interval))
            connection.privmsg(self.channel, f"Feed updated. Now cycling {url} every {interval} seconds.")
        except ValueError:
            logging.error('Invalid !feed command format')
            connection.privmsg(event.target, "Usage: !feed <feed url> <interval>")

    def command_status(self, connection):
        self.info_handler.get_status(connection)

    def command_rehash(self, connection):
        try:
            # Reload the configuration, keywords, and phrases
            self.bot.cmd_handler.bot.config.read('config.ini')
            self.bot.cmd_handler.bot.rss_handler.load_keywords_and_phrases()
            self.bot.cmd_handler.bot.rss_handler.rss_feed = self.bot.cmd_handler.bot.config.get('RSS', 'feed')
            self.bot.cmd_handler.bot.r
