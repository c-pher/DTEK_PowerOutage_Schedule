# Quick Start Guide 🚀

Get your power outage monitoring bot running in 5 minutes!

## Option 1: Python (Direct) 🐍

### Prerequisites

- Python 3.8+
- pip

### Steps

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**

   **Linux/macOS:**
   ```bash
   export TELEGRAM_BOT_TOKEN='your_bot_token'
   export TELEGRAM_CHANNEL_ID='@yourchannel'
   export GROUP_NUMBER='1.1'
   ```

   **Windows (PowerShell):**
   ```powershell
   $env:TELEGRAM_BOT_TOKEN='your_bot_token'
   $env:TELEGRAM_CHANNEL_ID='@yourchannel'
   $env:GROUP_NUMBER='1.1'
   ```

3. **Run the bot**
   ```bash
   python power_outage_bot.py
   ```

That's it! ✅

---

## How to Get Telegram Bot Token

1. Open Telegram
2. Search for `@BotFather`
3. Send: `/newbot`
4. Follow instructions
5. Copy the token (looks like: `123456789:ABCdefGHI...`)

## How to Get Channel ID

### For Public Channel:

- Just use: `@yourchannel`

### For Private Channel:

1. Forward any message from your channel to `@userinfobot`
2. It will show the channel ID (like: `-1001234567890`)
3. Use that ID

## Make Bot Admin in Channel

1. Open your channel
2. Go to channel info → Administrators
3. Add your bot
4. Give it "Post Messages" permission

## Finding Your Group Number

Your group number should be one of:

- **1.1, 1.2** - Group 1
- **2.1, 2.2** - Group 2
- **3.1, 3.2** - Group 3
- **4.1, 4.2** - Group 4
- **5.1, 5.2** - Group 5
- **6.1, 6.2** - Group 6

Check your electricity bill or ДТЕК official sources to find your group.

## Verification Checklist ✓

- [ ] Bot token is correct (from @BotFather)
- [ ] Bot is added as admin to channel
- [ ] Bot has "Post Messages" permission
- [ ] Channel ID is correct format
- [ ] Group number is valid (1.1 - 6.2)
- [ ] Bot logs show "Bot started for group X.X"
- [ ] No error messages in logs

## Common Issues

### "Chat not found"

- Channel ID is wrong
- Bot is not admin in the channel

### "No data found for group"

- Group number format is wrong (use dots: 1.1, not 11)

### Bot runs but no messages

- Bot is working, waiting for schedule changes
- Check state file: `outage_state.json`

## Need Help?

1. Check full README.md for detailed instructions
2. Verify all steps in the checklist above
3. Check bot logs for error messages
4. Make sure data source is accessible: https://github.com/Baskerville42/outage-data-ua

---

🇺🇦 Stay informed, stay safe!
