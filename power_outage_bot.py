__author__ = 'Andrey Komissarov'
__date__ = '06.11.2025'

"""
Kyiv Power Outage Monitoring Telegram Bot
Monitors power outage schedules and posts updates to a Telegram channel
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional, Dict, List

import aiohttp
from loguru import logger
from telegram import Bot
from telegram.error import TelegramError

# Configuration
TELEGRAM_BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'
TELEGRAM_CHANNEL_ID = ''
GROUP_NUMBER = '2.2'

DATA_URL = 'https://raw.githubusercontent.com/Baskerville42/outage-data-ua/refs/heads/main/data/kyiv.json'
GROUP_NUMBER_URL = GROUP_NUMBER.replace('.', '-')
PICTURE_URL = (f'https://raw.githubusercontent.com/Baskerville42/outage-data-ua/refs/heads/main/images/kyiv/'
               f'gpv-{GROUP_NUMBER_URL}-emergency.png')
STATE_FILE = 'outage_state.json'
CHECK_INTERVAL = 900  # 15 minutes in seconds

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
        self.group_key = f'GPV{group_number}'
        self.group_display = f'Черга {group_number}'

        logger.info('=' * 60)
        logger.info(f'Bot started for group {self.group_display}')
        logger.info(f'Posting to channel: {self.channel_id[:5]}...')
        logger.info('=' * 60)

    @staticmethod
    async def fetch_data() -> Optional[Dict]:
        """Fetch the latest outage data from GitHub"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(DATA_URL, timeout=30) as response:
                    if response.status == 200:
                        # Ignore content type check for GitHub raw URLs.
                        # Otherwise, use .text() + json.loads(text) instead of .json()
                        json_data = await response.json(content_type=None)
                        return json_data
                    else:
                        logger.error(f'Failed to fetch data: HTTP {response.status}')
                        return None
        except Exception as e:
            logger.error(f'Error fetching data: {e}')
            return None

    @staticmethod
    def load_state() -> Dict:
        """Load the previous state from file"""

        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f'Error loading state: {e}')
            return {}

    @staticmethod
    def save_state(state: Dict):
        """Save the current state to file"""

        try:
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info('State saved successfully')
        except Exception as e:
            logger.error(f'Error saving state: {e}')

    @staticmethod
    def calculate_duration(time_range: str) -> float:
        """Calculate duration in hours from time range like '19:00-22:00'"""

        # noinspection PyBroadException
        try:
            start, end = time_range.split('-')
            start_h, start_m = map(int, start.split(':'))
            end_h, end_m = map(int, end.split(':'))

            start_total = start_h + start_m / 60
            end_total = end_h + end_m / 60

            # Handle case where end time is 24:00 (midnight)
            if end_h == 24:
                end_total = 24

            duration = end_total - start_total
            return duration
        except:
            return 0

    @staticmethod
    def format_duration(hours: float) -> str:
        """Format duration in human readable format"""

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
        """Merge continuous time periods
        e.g., ['17:30-18:00 (30 хв)', '18:00-21:00 (3 год)']
        becomes ['17:30-21:00 (3 год 30 хв)']
        """
        if not outages:
            return []

        merged = []
        i = 0

        while i < len(outages):
            # Extract start time, end time from current period
            current = outages[i]
            # Remove duration part to work with time range only

            time_part = current.split(' (')[0]
            start_time, end_time = time_part.split('-')

            # Look ahead and merge if continuous
            j = i + 1
            while j < len(outages):
                next_period = outages[j]
                next_time_part = next_period.split(' (')[0]
                next_start, next_end = next_time_part.split('-')

                # Check if end of current equals start of next
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

            # Move to next unmerged period
            i = j

        return merged

    def parse_schedule(self, hours_data: Dict[str, str]) -> List[str]:
        """Parse hourly data into readable time ranges with duration

        Note: Hour number represents END of period
        e.g., '11': 'no' means 10:00-11:00 (no power from 10 till 11)
              '18': 'second' means 18:30-19:00 (no power second half of hour 18)
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

    def format_message(self, today_outages: List[str], tomorrow_outages: Optional[List[str]],
                       today_date: str, tomorrow_date: str = None, is_update: bool = False) -> str:
        """Format the message for Telegram"""

        emoji = '🔄' if is_update else '⚡'
        title = 'ОНОВЛЕННЯ графіка відключень' if is_update else 'Графік відключень'
        msg = f'{emoji} <b>{title} ({self.group_display})</b>\n\n'

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
        """Send message to Telegram channel"""

        # Add timestamp to bypass Telegram cache
        cache_buster = int(time.time())
        separator = '&' if '?' in PICTURE_URL else '?'
        picture_url_no_cache = f'{PICTURE_URL}{separator}t={cache_buster}'

        logger.info(f'Sending photo: {picture_url_no_cache}')

        try:
            await self.bot.send_photo(
                chat_id=self.channel_id,
                photo=picture_url_no_cache,
                caption=message,
                parse_mode='HTML'
            )
            logger.info('Message sent successfully')
        except TelegramError as e:
            logger.error(f'Failed to send message: {e}')

    @staticmethod
    def get_date_string(timestamp: int) -> str:
        """Convert timestamp to date string"""

        return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y')

    async def check_and_notify(self):
        """Check for updates and send notifications"""

        logger.info('Checking for updates...')

        # Fetch latest data
        data = await self.fetch_data()
        if not data or 'fact' not in data:
            logger.warning('No valid data received')
            return

        # Load previous state
        prev_state = self.load_state()

        # Extract data
        fact_data = data['fact']['data']
        today_timestamp = data['fact']['today']

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

        # Create current state
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

        if is_first_run:
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

            # Check if date changed (new day)
            if prev_state.get('today', {}).get('date') != today_date:
                has_changes = True
                logger.info('New day detected')

        # Send notification if there are changes
        if has_changes:
            message = self.format_message(
                today_outages,
                tomorrow_outages,
                today_date,
                tomorrow_date,
                is_update=(not is_first_run)
            )
            await self.send_message(message)
        else:
            logger.info('No changes detected')

        # Save current state
        self.save_state(current_state)

    async def run(self):
        """Main monitoring loop"""
        logger.info(f'Starting monitoring loop (checking every {CHECK_INTERVAL} seconds)')

        while True:
            try:
                await self.check_and_notify()
            except Exception as e:
                logger.error(f'Error in monitoring loop: {e}')

            # Wait before next check
            logger.info(f'Waiting {CHECK_INTERVAL} seconds until next check...')
            await asyncio.sleep(CHECK_INTERVAL)


# noinspection PyPep8Naming
async def main():
    """Main function to run the bot"""

    # Get configuration from environment variables or use defaults
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', TELEGRAM_BOT_TOKEN)
    CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', TELEGRAM_CHANNEL_ID)
    DTEK_GROUP_NUMBER = os.getenv('GROUP_NUMBER', GROUP_NUMBER)

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

    # Create and run monitor
    monitor = PowerOutageMonitor(BOT_TOKEN, CHANNEL_ID, DTEK_GROUP_NUMBER)

    try:
        await monitor.run()
    except KeyboardInterrupt:
        logger.info('Bot stopped by user')
    except Exception as e:
        logger.error(f'Fatal error: {e}')


if __name__ == '__main__':
    asyncio.run(main())
