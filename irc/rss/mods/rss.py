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
        # No need to define channels in config.ini anymore
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
        logging.info('Keywords and phrases reloaded.')

    def start_cycle(self, connection):
        if not self.cycle_active:
            self.cycle_active = True
            self.cycle_thread = Thread(target=self.check_feed, args=(connection,))
            self.cycle_thread.start()
            logging.info('Started cycling feed: %s', self.rss_feed)
            # Send a message to the first channel in the keywords.json
            connection.privmsg(list(self.keywords.keys())[0], "Cycling current feed.")
        else:
            connection.privmsg(list(self.keywords.keys())[0], "Feed is already cycling.")

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
        summary = clean_html(entry.get('summary', ''))

        for channel, keywords in self.keywords.items():
            # Check if any keyword in the list is present in the title
            for keyword in keywords:
                if keyword.lower() in title.lower():
                    message_template = self.keywords[channel]["message_template"]  # Access message template
                    if message_template is None:
                        message_template = "{title} - {link}"  # Default message template if not specified

                    message = message_template.format(
                        title=title,
                        link=link,
                        description=description,
                        summary=summary,
                        keyword=keyword  # Use the matched keyword
                    )

                    message_with_trigger = f"{message} (Triggered by: '{keyword}')"
                    total_length = len(message_with_trigger) + len(channel) + SAFETY_MARGIN

                    if total_length > MAX_MESSAGE_LENGTH:
                        excess_length = total_length - MAX_MESSAGE_LENGTH
                        if len(description) > excess_length:
                            description = description[:-(excess_length + 3)] + '...'
                        else:
                            summary = summary[:-(excess_length + 3)] + '...'

                        message = message_template.format(
                            title=title,
                            link=link,
                            description=description,
                            summary=summary,
                            keyword=keyword
                        )
                        message_with_trigger = f"{message} (Triggered by: '{keyword}')"

                    if len(message_with_trigger) > MAX_MESSAGE_LENGTH:
                        message_with_trigger = message_with_trigger[:MAX_MESSAGE_LENGTH - 3] + "..."

                    logging.info('Posting to channel %s: %s', channel, message_with_trigger)
                    connection.privmsg(channel, message_with_trigger)
                    return  # Exit after the first match to avoid multiple posts for the same entry
