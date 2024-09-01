import feedparser
import logging
import time
import json
import re
from threading import Thread

MAX_MESSAGE_LENGTH = 512  # Maximum allowed length for IRC messages
SAFETY_MARGIN = 20  # Safety margin to ensure we stay well below the limit

def clean_html(raw_html):
    """Remove HTML tags and decode HTML entities."""
    clean_text = re.sub('<.*?>', '', raw_html)
    return re.sub('&[a-zA-Z0-9#]+;', '', clean_text)

class RSSHandler:
    def __init__(self, irc_client, config):
        self.irc_client = irc_client
        self.config_channel = config.get('IRC', 'channel')
        self.rss_feed = config.get('RSS', 'feed')
        self.check_interval = config.getint('RSS', 'check_interval')
        self.cycle_active = False
        self.cycle_thread = None

        # Load keywords and phrases
        self.load_keywords_and_phrases()

    def load_keywords_and_phrases(self):
        """Loads keywords and phrases from JSON files."""
        with open('keywords.json', 'r') as f:
            self.keywords = json.load(f)
        with open('phrases.json', 'r') as f:
            self.phrases = json.load(f)
        logging.info('Keywords and phrases reloaded.')

    def start_cycle(self, connection):
        if not self.cycle_active:
            self.cycle_active = True
            self.cycle_thread = Thread(target=self.check_feed, args=(connection,))
            self.cycle_thread.start()
            logging.info('Started cycling feed: %s', self.rss_feed)
            connection.privmsg(self.config_channel, "Cycling current feed.")
        else:
            connection.privmsg(self.config_channel, "Feed is already cycling.")

    def check_feed(self, connection):
        seen_entries = set()
        while self.cycle_active:
            feed = feedparser.parse(self.rss_feed)
            logging.debug('Checking feed: %s', self.rss_feed)
            for entry in feed.entries:
                if entry.id not in seen_entries:
                    seen_entries.add(entry.id)
                    self.process_entry(entry, connection)
            time.sleep(self.check_interval)

    def process_entry(self, entry, connection):
        title = entry.title
        link = entry.link
        description = clean_html(entry.get('description', 'No description available.'))
        summary = clean_html(entry.get('summary', ''))  # Extract summary with a default empty string

        for channel, words in self.keywords.items():
            for word in words:
                if word.lower() in title.lower():
                    phrase_data = self.phrases.get(channel, self.phrases['default'])
                    target_channel = channel  # Use the channel associated with the keyword

                    message_template = phrase_data["message_template"]
                    message = message_template.format(
                        title=title,
                        link=link,
                        description=description,
                        summary=summary,
                        keyword=word
                    )

                    # Calculate the length of the final message
                    message_with_trigger = f"{message} (Triggered by: '{word}')"
                    total_length = len(message_with_trigger) + len(target_channel) + SAFETY_MARGIN

                    # Truncate if necessary
                    if total_length > MAX_MESSAGE_LENGTH:
                        excess_length = total_length - MAX_MESSAGE_LENGTH
                        if len(description) > excess_length:
                            description = description[:-(excess_length + 3)] + '...'
                        else:
                            summary = summary[:-(excess_length + 3)] + '...'

                        # Rebuild the message after truncation
                        message = message_template.format(
                            title=title,
                            link=link,
                            description=description,
                            summary=summary,
                            keyword=word
                        )
                        message_with_trigger = f"{message} (Triggered by: '{word}')"

                    # Ensure the final message is within the IRC limit
                    if len(message_with_trigger) > MAX_MESSAGE_LENGTH:
                        message_with_trigger = message_with_trigger[:MAX_MESSAGE_LENGTH - 3] + "..."

                    logging.info('Posting to channel %s: %s', target_channel, message_with_trigger)
                    connection.privmsg(target_channel, message_with_trigger)
                    return  # Exit after the first match to avoid multiple posts for the same entry

    def parse_feed_once(self, connection, url):
        logging.info('Parsing feed once for URL: %s', url)
        feed = feedparser.parse(url)
        seen_entries = set()
        for entry in feed.entries:
            if entry.id not in seen_entries:
                seen_entries.add(entry.id)
                self.process_entry(entry, connection)

    def update_feed(self, url, interval):
        self.rss_feed = url
        self.check_interval = interval
        logging.info('Updated RSS feed to: %s with interval: %d', url, interval)

    def testrss(self, connection, url):
        """Test an RSS feed and output available properties of the first entry."""
        logging.info('Testing RSS feed: %s', url)
        feed = feedparser.parse(url)
        if feed.entries:
            entry = feed.entries[0]
            connection.privmsg(self.config_channel, "Available properties for the first entry:")
            for key, value in entry.items():
                # Convert non-string values to strings for output
                if not isinstance(value, str):
                    value = str(value)
                truncated_value = value if len(value) <= 300 else value[:297] + "..."
                connection.privmsg(self.config_channel, f"{key}: {truncated_value}")
                logging.info('%s: %s', key, truncated_value)
        else:
            connection.privmsg(self.config_channel, "No entries found in the RSS feed.")
            logging.info('No entries found in the RSS feed: %s', url)
