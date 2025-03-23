# Telegram Channel Finder

This tool extracts channel/group links from Telegram user profiles and bios.

## Setup

1. Get your Telegram API credentials (API_ID and API_HASH) from https://my.telegram.org
2. Copy them to the `.env` file
3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Create a file named `accounts.txt` with Telegram usernames or IDs (one per line)
2. Run the script:
```bash
python channel_finder.py
```
3. Found channels will be saved in `channels.txt`

## Input Format

`accounts.txt` supports these formats:
- Numeric IDs: `1132531771`
- Usernames: `@username`
- Links: `https://t.me/username`

## Output

`channels.txt` will contain channel/group identifiers, one per line.