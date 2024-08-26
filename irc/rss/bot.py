import configparser
import ssl
import logging
import irc.client
from threading import Thread

# Import modules from mods
from mods.rss import RSSHandler
from mods.info import InfoHandler
from mods.cmd import CommandHandler

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

class RSSIRCBot:
    def __init__(self):
        self.config = config  # Ensure config is accessible
        self.server = self.config.get('IRC', 'server')
        self.port = self.config.getint('IRC', 'port')
        self.use_ssl = self.config.getboolean('IRC', 'use_ssl')
        self.channel = self.config.get('IRC', 'channel')
        self.nickname = self.config.get('IRC', 'nickname')
        self.realname = self.config.get('IRC', 'realname')

        self.irc_client = irc.client.Reactor()
        self.initialize_modules()

    def initialize_modules(self):
        """Initialize all modules."""
        self.rss_handler = RSSHandler(self.irc_client, self.config)
        self.info_handler = InfoHandler(self.irc_client, self.config)
        self.cmd_handler = CommandHandler(self, self.config)
        logging.info('Modules initialized.')

    def on_connect(self, connection, event):
        if irc.client.is_channel(self.channel):
            connection.join(self.channel)
            logging.info('Connected to IRC channel: %s', self.channel)

    def on_disconnect(self, connection, event):
        logging.warning('Disconnected from server')
        raise SystemExit()

    def on_join(self, connection, event):
        logging.info('Joined channel: %s', self.channel)

    def on_privmsg(self, connection, event):
        self.handle_command(connection, event, event.arguments[0].strip())

    def on_pubmsg(self, connection, event):
        self.handle_command(connection, event, event.arguments[0].strip())

    def handle_command(self, connection, event, message):
        logging.debug('Received command: %s', message)
        self.cmd_handler.process_command(connection, event, message)

    def on_ping(self, connection, event):
        connection.pong(event.target)

    def run(self):
        try:
            if self.use_ssl:
                # Explicitly set the SSL context to use TLSv1.2
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
                ssl_context.verify_mode = ssl.CERT_NONE  # Modify if the server requires certificate validation

                ssl_factory = irc.connection.Factory(wrapper=ssl_context.wrap_socket)
                connection = self.irc_client.server().connect(
                    self.server, self.port, self.nickname, self.realname, connect_factory=ssl_factory
                )
            else:
                connection = self.irc_client.server().connect(
                    self.server, self.port, self.nickname, self.realname
                )

            connection.add_global_handler("welcome", self.on_connect)
            connection.add_global_handler("join", self.on_join)
            connection.add_global_handler("privmsg", self.on_privmsg)
            connection.add_global_handler("pubmsg", self.on_pubmsg)
            connection.add_global_handler("disconnect", self.on_disconnect)
            connection.add_global_handler("ping", self.on_ping)  # Handle PING/PONG

            logging.info('Bot is running and waiting for commands')
            self.irc_client.process_forever()

        except irc.client.ServerConnectionError as e:
            logging.critical('Connection failed: %s', e)
            print(f"Connection failed: {e}")

    def rehash(self, connection):
        """Rehash the bot: reload config and reinitialize all modules."""
        try:
            self.config.read('config.ini')
            self.initialize_modules()
            connection.privmsg(self.channel, "Configuration and modules reloaded successfully.")
            logging.info('Configuration and modules reloaded successfully.')
        except Exception as e:
            connection.privmsg(self.channel, f"Failed to rehash: {str(e)}")
            logging.error('Failed to rehash: %s', str(e))

if __name__ == '__main__':
    bot = RSSIRCBot()
    bot.run()
