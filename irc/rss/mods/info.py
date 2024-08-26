import psutil
import logging

class InfoHandler:
    def __init__(self, irc_client, config):
        self.irc_client = irc_client
        self.channel = config.get('IRC', 'channel')

    def get_status(self, connection, rss_feed, check_interval):
        cpu_usage = psutil.cpu_percent(interval=1)
        ram_usage = psutil.virtual_memory().percent
        message = f"Status: CPU {cpu_usage}%, RAM {ram_usage}%, Feed: {rss_feed}, Interval: {check_interval}s"
        logging.debug('Status: %s', message)
        connection.privmsg(self.channel, message)
