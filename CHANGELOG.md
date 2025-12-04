[1.0.0] – 2025-12-04

Added
• Initial release of the Telegram bot for monitoring DTEK power outage schedules (Kyiv).
• Support for outage groups 1.1–6.2.
• Automatic schedule update checks every ~15 minutes.
• Notifications to a Telegram channel when the schedule changes.
• Display of outage schedule for today and tomorrow.
• All bot messages provided in Ukrainian language.
• Configuration via environment variables:
• TELEGRAM_BOT_TOKEN
• TELEGRAM_CHANNEL_ID
• GROUP_NUMBER
• State file outage_state.json used to track previous schedule and detect changes.
• Deployment instructions included for:
• direct Python script execution
• systemd service
• Docker (Dockerfile included)

Known Issues
• Deleting outage_state.json resets the stored previous schedule history.
• Incorrect GROUP_NUMBER or missing bot permissions in the Telegram channel result in no notifications being sent.
• The bot relies on an external data source; schedule updates depend on its accuracy and availability.
