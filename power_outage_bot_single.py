__author__ = 'Andrey Komissarov'
__date__ = '06.11.2025'

"""
Kyiv Power Outage Monitoring Telegram Bot
Monitors power outage schedules and posts updates to a Telegram channel
"""

import asyncio
import aiohttp
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional, Dict, List
from loguru import logger
from telegram import Bot
from telegram.error import TelegramError

# Logger settings
log_file_name = 'bot.log'
log_path = f'./logs/{log_file_name}'
fmt = '<green>{time: YYYY-MM-DD at HH:mm:ss.SSSS}</> | <lvl>{level: <7}</> | {function}:{line} | {message}'
config = {
    'handlers': [
        {
            'sink': sys.stdout,
            'level': 'DEBUG',
            'format': fmt,
            'colorize': True,
        },
        {
            'sink': log_path,
            'level': 'DEBUG',
            'format': fmt,
            # 'serialize': True,
            'backtrace': True,
            'rotation': '10 MB',
            'retention': '1h',  # 3 days
            'compression': 'zip',
        },
    ],
}
logger.configure(**config)


class PowerOutageMonitor:
    def __init__(self, bot_token: str, channel_id: str, group_number: str):
        """
        Initialize the power outage monitor

        Args:
            bot_token: Telegram bot token from @BotFather
            channel_id: Telegram channel ID (e.g., @yourchannel or -1001234567890)
            group_number: Group to monitor (e.g., '1.1', '2.2', etc.)
        """

        self.bot = Bot(token=bot_token)
        self.channel_id = channel_id
        self.group_number = group_number

        self.group_key = f'GPV{self.group_number}'
        self.group_display = f'Черга {self.group_number}'

        self.data_url = 'https://raw.githubusercontent.com/Baskerville42/outage-data-ua/refs/heads/main/data/kyiv.json'
        self.state_file = 'outage_state.json'

        logger.info('=' * 60)
        logger.info(f'Bot started for group {self.group_display}')
        logger.info(f'Posting to channel: {self.channel_id[:5]}...')
        logger.info('=' * 60)

    async def fetch_data(self) -> Optional[Dict]:
        """
        Fetches data asynchronously from a specified URL and returns it in JSON format.
        Handles exceptions and logs errors if the request fails or encounters issues.

        Returns:
            Optional[Dict]: Parsed JSON data from the API response if the request
            is successful, or None if there is an error or a non-200 HTTP status code.
        """

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.data_url, timeout=30) as response:
                    if response.status == 200:
                        # Ignore content type check for GitHub raw URLs.
                        # Otherwise, use .text() + json.loads(text) instead of .json()
                        json_data = await response.json(content_type=None)
                        return json_data
                    else:
                        logger.error(f'Failed to fetch data: HTTP {response.status}')
                        return None
        except Exception as err:
            logger.error(f'Error fetching data: {err}')
            return None

    def get_photo_url(self):
        """
        Generates a URL for retrieving a photo based on the group number.

        The method constructs the URL by transforming the `group_number` attribute
        to replace periods with dashes and appending it to a predefined path for
        retrieving corresponding group photos.

        Returns:
            str: A formatted URL string pointing to the photo resource.
        """

        group_number_with_dash = self.group_number.replace('.', '-')
        photo_url = (f'https://raw.githubusercontent.com/Baskerville42/outage-data-ua/refs/heads/main/images/kyiv/'
                     f'gpv-{group_number_with_dash}-emergency.png')

        return photo_url

    def load_state(self) -> Dict:
        """
        Loads the application state from a predefined state file if it exists.

        This method checks for the existence of a specified state file and reads
        its contents to return the saved state as a dictionary object. If the
        state file does not exist or an exception occurs during loading, it
        returns an empty dictionary. All exceptions encountered are logged for
        diagnostic purposes.

        Returns:
            Dict: A dictionary containing the state data loaded from the state
            file, or an empty dictionary if the file does not exist or an error
            occurs.
        """

        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f'Error loading state: {e}')
            return {}

    def save_state(self, state: Dict):
        """
        Saves the provided state dictionary to a file in JSON format. Ensures the
        file is encoded in UTF-8, with keys and values formatted neatly using an
        indentation level of 2 spaces.

        Args:
            state (Dict): The dictionary containing the state to be saved.
        """

        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info('State saved successfully')
        except Exception as err:
            logger.error(f'Error saving state: {err}')

    @staticmethod
    def calculate_duration(time_range: str) -> float:
        """
        Calculates the duration between two times provided in a specific time range
        format. The time range is expected to be in the format 'HH:MM-HH:MM'.
        The method handles edge cases, such as the end time being 24:00, to
        represent midnight. Returns 0 in case of any format or calculation errors.

        Parameters:
            time_range (str): A string representing the time range in "HH:MM-HH:MM" format.

        Returns:
            float: The calculated duration in hours.
        """

        # noinspection PyBroadException
        try:
            start, end = time_range.split('-')
            start_h, start_m = map(int, start.split(':'))
            end_h, end_m = map(int, end.split(':'))

            start_total = start_h + start_m / 60
            end_total = end_h + end_m / 60

            # Handle case where the end time is 24:00 (midnight)
            if end_h == 24:
                end_total = 24

            duration = end_total - start_total
            return duration
        except:
            return 0

    @staticmethod
    def format_duration(hours: float) -> str:
        """
        Formats the duration given in hours into a string representing the duration
        in Ukrainian language using hours and/or minutes. This method provides
        localized representation of time intervals based on varying conditions.

        Args:
            hours: Floating-point value representing the duration in hours.
                   It can be fractional or an integer.

        Returns:
            A string formatted to represent the duration in the Ukrainian language.
            For instance, durations can be expressed as "30 хв" for 0.5 hours,
            "1 год" for 1 hour, "X год Y хв" for mixed hours and minutes, or only
            hours or minutes if applicable.
        """

        if hours == 0.5:
            return '30 хв'
        elif hours == 1:
            return '1 год'
        elif hours < 1:
            minutes = int(hours * 60)
            return f'{minutes} хв'
        elif hours == int(hours):
            return f'{int(hours)} год'
        else:
            whole_hours = int(hours)
            minutes = int((hours - whole_hours) * 60)
            return f'{whole_hours} год {minutes} хв'

    # noinspection PyUnresolvedReferences
    def merge_continuous_periods(self, outages: List[str]) -> List[str]:
        """
        Merges a list of continuous time periods into a single consolidated list.

        This method takes a list of time periods, each formatted as a string containing
        a time range and a duration (e.g., '08:00-09:00 (1h)'). It merges periods where
        the end of one period matches the start of the next into a single period while
        updating the total duration. It ensures that the modified list preserves accuracy
        and consistency in duration calculation.

        e.g., ['17:30-18:00 (30 хв)', '18:00-21:00 (3 год)']
        becomes ['17:30-21:00 (3 год 30 хв)']

        Parameters:
            outages: List of time periods as strings, each representing a time range
                     and duration to be processed for merging.

        Returns:
            List of merged time periods as strings, where overlapping or continuous
            periods are combined into one with the updated duration.

        """
        if not outages:
            return []

        merged = []
        i = 0

        while i < len(outages):
            # Extract start time, end time from the current period
            current = outages[i]
            # Remove the duration part to work with time range only

            time_part = current.split(' (')[0]
            start_time, end_time = time_part.split('-')

            # Look ahead and merge if continuous
            j = i + 1
            while j < len(outages):
                next_period = outages[j]
                next_time_part = next_period.split(' (')[0]
                next_start, next_end = next_time_part.split('-')

                # Check if the end of current equals start of next
                if end_time == next_start:
                    # Merge: extend end_time
                    end_time = next_end
                    j += 1
                else:
                    break

            # Calculate total duration for merged period
            merged_range = f'{start_time}-{end_time}'
            duration = self.calculate_duration(merged_range)
            merged.append(f'{merged_range} ({self.format_duration(duration)})')

            # Move to the next unmerged period
            i = j

        return merged

    def parse_schedule(self, hours_data: Dict[str, str]) -> List[str]:
        """
        Parses the given schedule data to identify time intervals during which outages occur.
        This method processes the input dictionary of hourly statuses, determines outage
        intervals, their durations, and formats them into human-readable strings. It also
        merges continuous periods of outages to simplify reporting.

        Parameters:
            hours_data: Dict[str, str]
                A dictionary representing the hourly schedule data where keys are hour
                numbers as strings (1 to 24), and values indicate the status for the
                corresponding hour. The possible values for the statuses are:
                - 'yes': Indicates no outage for the hour.
                - 'no': Indicates an outage for the entire hour.
                - 'first': Indicates an outage for the first half of the hour
                  (0 to 30 minutes past the hour).
                - 'second': Indicates an outage for the second half of the hour
                  (30 to 60 minutes past the hour).

        Returns:
            List[str]: A list of strings where each string represents a time interval
            with its corresponding outage duration. The intervals are formatted as
            '[start_time]-[end_time] ([duration])'.
        """

        if not hours_data:
            return []

        outages = []
        i = 1
        while i <= 24:
            status = hours_data.get(str(i), 'yes')

            if status == 'no':
                # Find continuous 'no' periods
                # Hour i means period (i-1):00 to i:00
                start = i - 1
                while i <= 24 and hours_data.get(str(i), 'yes') == 'no':
                    i += 1
                end = i - 1
                time_range = f'{start:02d}:00-{end:02d}:00'
                duration = self.calculate_duration(time_range)
                outages.append(f'{time_range} ({self.format_duration(duration)})')
            elif status == 'first':
                # First half: (i-1):00 to (i-1):30
                time_range = f'{i - 1:02d}:00-{i - 1:02d}:30'
                duration = self.calculate_duration(time_range)
                outages.append(f'{time_range} ({self.format_duration(duration)})')
                i += 1
            elif status == 'second':
                # Second half: (i-1):30 to i:00
                time_range = f'{i - 1:02d}:30-{i:02d}:00'
                duration = self.calculate_duration(time_range)
                outages.append(f'{time_range} ({self.format_duration(duration)})')
                i += 1
            else:
                i += 1

        # Merge continuous periods
        return self.merge_continuous_periods(outages)

    @staticmethod
    def format_message(today_outages: List[str], tomorrow_outages: Optional[List[str]],
                       today_date: str, tomorrow_date: str = None,
                       last_updated: str = None, is_update: bool = False) -> str:
        """
        Formats a message detailing the outage schedule for today and tomorrow, optionally with an update indicator.

        The method generates a formatted string containing the outage schedule for the specified dates, including
        whether the schedule has been last_updated, and indicating planned outages with specific periods. The returned
        message includes separate sections for today's and tomorrow's schedules, if applicable.

        Parameters:
            today_outages (List[str]): List of outage periods for today.
            tomorrow_outages (Optional[List[str]]): Optional list of outage periods for tomorrow. If None, no information about
                tomorrow will be included in the message.
            today_date (str): The date for today in string format.
            tomorrow_date (str, optional): The date for tomorrow in string format. Default is None, meaning no tomorrow's
                information will be included if tomorrow_outages is also None.
            last_updated (str, optional): Indicates when the schedule has been updated. Data from DTEK
            is_update (bool, optional): Indicator whether the schedule is an update. If True, the message title will include
                update information. Default is False.

        Returns:
            str: A formatted string representing the outage schedule message.
        """

        emoji = '🔄' if is_update else '⚡'
        title = 'ОНОВЛЕННЯ графіка відключень' if is_update else 'Графік відключень'
        msg = f'{emoji} <b>{title}</b>\n'
        msg += f'🕐 Оновлено: {last_updated}\n\n'

        # Today's schedule
        msg += f'<b>📅 Сьогодні ({today_date}):</b>\n'
        if today_outages:
            msg += '🔴 Відключення:\n'
            for period in today_outages:
                msg += f'<code>{period}</code>\n'
        else:
            msg += '✅ Відключення не заплановані\n'

        # Tomorrow's schedule
        if tomorrow_outages is not None:
            msg += f'\n<b>📅 Завтра ({tomorrow_date}):</b>\n'
            if tomorrow_outages:
                msg += '🔴 Відключення:\n'
                for period in tomorrow_outages:
                    msg += f'<code>{period}</code>\n'
            else:
                msg += '✅ Відключення не заплановані\n'

        msg += '\n<i>Джерело: ДТЕК</i>'
        return msg

    async def send_message(self, message: str):
        """
        Sends a photo with a message to a specific Telegram channel.

        Adds a timestamp to the photo URL to bypass Telegram's caching mechanism and sends it alongside
        a provided message to a Telegram channel using the bot instance. Logs the sending process and any
        errors encountered.

        Parameters:
            message (str): The message caption to be sent along with the photo.

        Raises:
            TelegramError: If sending the photo message fails.
        """

        # Add timestamp to bypass Telegram cache
        cache_buster = int(time.time())
        photo_url = self.get_photo_url()
        photo_url_no_cache = f'{photo_url}?t={cache_buster}'

        logger.info(f'Sending photo: {photo_url_no_cache}')

        try:
            await self.bot.send_photo(
                chat_id=self.channel_id,
                photo=photo_url_no_cache,
                caption=message,
                parse_mode='HTML'
            )
            logger.info('Message sent successfully')
        except TelegramError as e:
            logger.error(f'Failed to send message: {e}')

    @staticmethod
    def get_date_string(timestamp: int) -> str:
        """
        Converts a Unix timestamp to a formatted date string.

        This static method takes a Unix timestamp as an argument and returns a string
        representation of the date in the format 'dd.mm.yyyy'.

        Args:
            timestamp (int): The Unix timestamp to be converted.

        Returns:
            str: A human-readable date string in the format 'dd.mm.yyyy'.
        """

        return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y')

    async def check_and_notify(self):
        """
        Performs the check for updates, compares the current and previous states, and sends a notification
        if necessary. The function gathers schedule data, identifies outages for today and tomorrow, and
        determines any changes between states, optionally forced by an environment variable. Updates are
        sent based on the detected changes or initial conditions, and the current state is saved.
        """

        logger.info('Checking for updates...')

        # Check for force send the flag
        force_send = os.getenv('FORCE_SEND', 'false').lower() in ('true', '1', 'yes')
        if force_send:
            logger.info('⚠️ FORCE_SEND is enabled - will send message regardless of changes')

        # Fetch latest data
        data = await self.fetch_data()
        if not data or 'fact' not in data:
            logger.warning('No valid data received')
            return

        # Load previous state
        prev_state = self.load_state()

        # Extract data
        try:
            fact_data = data['fact']['data']
            last_updated = data['fact']['update']
            today_timestamp = data['fact']['today']
        except KeyError as err:
            logger.error(f'Missing key in data: {err}')
            return

        # Get timestamps
        timestamps = sorted([int(ts) for ts in fact_data.keys()])

        # Find today and tomorrow data
        today_data = fact_data.get(str(today_timestamp), {}).get(self.group_key)
        tomorrow_timestamp = None
        tomorrow_data = None

        if len(timestamps) > 1:
            for ts in timestamps:
                if ts > today_timestamp:
                    tomorrow_timestamp = ts
                    tomorrow_data = fact_data.get(str(ts), {}).get(self.group_key)
                    break

        if not today_data:
            logger.warning(f'No data found for {self.group_key}')
            return

        # Parse schedules
        today_outages = self.parse_schedule(today_data)
        tomorrow_outages = self.parse_schedule(tomorrow_data) if tomorrow_data else None

        today_date = self.get_date_string(today_timestamp)
        tomorrow_date = self.get_date_string(tomorrow_timestamp) if tomorrow_timestamp else None

        # Create the current state
        current_state = {
            'today': {
                'date': today_date,
                'timestamp': today_timestamp,
                'outages': today_outages
            },
            'last_check': datetime.now().isoformat(),
            'last_update': data.get('lastUpdated', '')
        }

        if tomorrow_outages is not None:
            current_state['tomorrow'] = {
                'date': tomorrow_date,
                'timestamp': tomorrow_timestamp,
                'outages': tomorrow_outages
            }

        # Check if there are changes
        has_changes = False
        is_first_run = not prev_state

        if force_send:
            has_changes = True
            is_first_run = False  # Show as update, not first run
            logger.info('🔧 Forcing message send (FORCE_SEND=true)')
        elif is_first_run:
            has_changes = True
            logger.info('First run - sending initial notification')
        else:
            # Check for changes in today's schedule
            if prev_state.get('today', {}).get('outages') != today_outages:
                has_changes = True
                logger.info("Changes detected in today's schedule")

            # Check for changes in tomorrow's schedule
            if tomorrow_outages is not None:
                if prev_state.get('tomorrow', {}).get('outages') != tomorrow_outages:
                    has_changes = True
                    logger.info("Changes detected in tomorrow's schedule")

            # Check if the date changed (new day)
            if prev_state.get('today', {}).get('date') != today_date:
                has_changes = True
                logger.info('New day detected')

        # Send a notification if there are changes
        if has_changes:
            message = self.format_message(
                today_outages,
                tomorrow_outages,
                today_date,
                tomorrow_date,
                last_updated=last_updated,
                is_update=(not is_first_run)
            )
            await self.send_message(message)
        else:
            logger.info('No changes detected')

        # Save the current state
        self.save_state(current_state)


# noinspection PyPep8Naming
async def main():
    """Main function to run the bot"""

    # Get configuration from environment variables or use defaults
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '@yourchannel')
    GROUP_NUMBER = os.getenv('GROUP_NUMBER', '2.2')

    # Validate configuration
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error('Please set TELEGRAM_BOT_TOKEN environment variable')
        print('\nUsage:')
        print('1. Get bot token from @BotFather on Telegram')
        print('2. Set environment variables:')
        print('   export TELEGRAM_BOT_TOKEN=\'your_bot_token\'')
        print('   export TELEGRAM_CHANNEL_ID=\'@yourchannel\'')
        print('   export GROUP_NUMBER=\'1.1\'')
        print('3. Run the bot: python power_outage_bot.py')
        return

    # Create and run a monitor
    monitor = PowerOutageMonitor(BOT_TOKEN, CHANNEL_ID, GROUP_NUMBER)

    try:
        await monitor.check_and_notify()
        logger.info('Check completed successfully')
    except Exception as e:
        logger.error(f'Error during check: {e}')


if __name__ == '__main__':
    asyncio.run(main())
