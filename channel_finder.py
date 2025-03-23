import os
import re
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetFullChannelRequest, GetChannelsRequest
from telethon.tl.types import (
    PeerUser, InputPeerUser, UserFull, User, Channel, PeerChannel,
    InputPeerChannel, InputChannel, Chat, InputPeerChat
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

# Regular expressions for finding channel/group links
TELEGRAM_LINK_PATTERN = r'(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:joinchat/)?([a-zA-Z0-9_-]+)'
USERNAME_PATTERN = r'@([a-zA-Z0-9_]+)'

async def extract_channels_from_text(text):
    if not text:
        return set()
    
    channels = set()
    # Find t.me links
    links = re.finditer(TELEGRAM_LINK_PATTERN, text)
    for link in links:
        channels.add(link.group(1))
    
    # Find @username mentions
    usernames = re.finditer(USERNAME_PATTERN, text)
    for username in usernames:
        channels.add(username.group(1))
    
    return channels

async def get_channel_info(client, channel_id):
    try:
        # Try to get channel directly by ID
        try:
            channel = await client.get_entity(PeerChannel(channel_id))
            if hasattr(channel, 'username') and channel.username:
                print(f"Debug - Found channel username by PeerChannel: {channel.username}")
                return channel.username
        except Exception as e:
            print(f"Debug - PeerChannel method failed: {str(e)}")
        
        # Try with InputPeerChannel
        try:
            channel = await client.get_entity(InputPeerChannel(channel_id, 0))
            if hasattr(channel, 'username') and channel.username:
                print(f"Debug - Found channel username by InputPeerChannel: {channel.username}")
                return channel.username
        except Exception as e:
            print(f"Debug - InputPeerChannel method failed: {str(e)}")
        
        # Try with direct API call to get channel details
        try:
            # Get the full channel info using API
            result = await client(GetChannelsRequest([InputChannel(channel_id, 0)]))
            if result and result.chats:
                for chat in result.chats:
                    if hasattr(chat, 'username') and chat.username:
                        print(f"Debug - Found channel username by GetChannelsRequest: {chat.username}")
                        return chat.username
        except Exception as e:
            print(f"Debug - GetChannelsRequest method failed: {str(e)}")
            
        print(f"Debug - Channel found but couldn't get username for ID: {channel_id}")
    except Exception as e:
        print(f"Debug - All channel info methods failed for {channel_id}: {str(e)}")
    
    return None

async def get_linked_channel_from_chat_id(client, chat_id):
    """Specifically handle the linked_chat_id to get channel information"""
    try:
        # First try as a channel
        try:
            chat_entity = await client.get_entity(PeerChannel(chat_id))
        except:
            # If not a channel, try as a chat
            try:
                chat_entity = await client.get_entity(InputPeerChat(chat_id))
            except:
                # Last resort - try as user
                try:
                    chat_entity = await client.get_entity(PeerUser(chat_id))
                except Exception as e:
                    print(f"Debug - Failed to get entity for linked_chat_id {chat_id}: {str(e)}")
                    return None
        
        # If we successfully got the entity, extract username
        if hasattr(chat_entity, 'username') and chat_entity.username:
            print(f"Debug - Found linked channel username: {chat_entity.username}")
            return chat_entity.username
        elif isinstance(chat_entity, Channel):
            # Try to get more details if it's a channel but doesn't have username directly
            try:
                full_channel = await client(GetFullChannelRequest(chat_entity))
                if hasattr(full_channel.chats[0], 'username') and full_channel.chats[0].username:
                    print(f"Debug - Found linked channel username from full details: {full_channel.chats[0].username}")
                    return full_channel.chats[0].username
            except Exception as e:
                print(f"Debug - Failed to get full channel details: {str(e)}")
    
    except Exception as e:
        print(f"Debug - Error getting linked channel from chat ID {chat_id}: {str(e)}")
    
    return None

async def process_user(client, user_input):
    channels = set()
    try:
        # Handle numeric ID or username
        if user_input.startswith('https://t.me/'):
            user_input = user_input.split('/')[-1]
        elif user_input.startswith('@'):
            user_input = user_input[1:]
        
        # Convert numeric IDs to integer and handle differently
        if user_input.isdigit():
            user_id = int(user_input)
            try:
                input_user = InputPeerUser(user_id, access_hash=0)
                user = await client.get_entity(input_user)
            except:
                peer = PeerUser(user_id)
                user = await client.get_entity(peer)
        else:
            user = await client.get_entity(user_input)
        
        # Get full user info
        full_user_result = await client(GetFullUserRequest(user))
        full_user = full_user_result.full_user
        
        print(f"Debug - User info for {user_input}:")
        print(f"Debug - Full user type: {type(full_user)}")
        print(f"Debug - Has about: {hasattr(full_user, 'about') and full_user.about is not None}")
        
        # Print all available fields in full_user for more detailed debugging
        print(f"Debug - Available fields in full_user: {dir(full_user)}")
        
        # CRITICAL FIX 1: Handle linked_chat_id properly
        if hasattr(full_user, 'linked_chat_id') and full_user.linked_chat_id:
            print(f"Debug - Found linked_chat_id: {full_user.linked_chat_id}")
            linked_username = await get_linked_channel_from_chat_id(client, full_user.linked_chat_id)
            if linked_username:
                channels.add(linked_username)
                print(f"Debug - Added linked channel: {linked_username}")
        
        # CRITICAL FIX 2: Try to access other potential channel references
        for attr_name in ['channel_id', 'profile_channel', 'business_repo_id', 'folder_id', 'bot_info']:
            if hasattr(full_user, attr_name) and getattr(full_user, attr_name):
                value = getattr(full_user, attr_name)
                print(f"Debug - Found potential channel reference in {attr_name}: {value}")
                
                # If it's a numeric ID, try to get channel info
                if isinstance(value, int):
                    channel_username = await get_channel_info(client, value)
                    if channel_username:
                        channels.add(channel_username)
                        print(f"Debug - Added channel from {attr_name}: {channel_username}")
        
        # CRITICAL FIX 3: Try to directly check if the user has a channel
        try:
            # Use GetUserRequest to see if the user has a channel with the same username
            from telethon.tl.functions.users import GetUsersRequest
            result = await client(GetUsersRequest([user]))
            
            if result and hasattr(result[0], 'bot_inline_placeholder'):
                print(f"Debug - User has bot_inline_placeholder: {result[0].bot_inline_placeholder}")
                # This might indicate a related channel
        except Exception as e:
            print(f"Debug - GetUsersRequest failed: {str(e)}")
        
        # Extract channels from bio
        if full_user.about:
            bio_channels = await extract_channels_from_text(full_user.about)
            channels.update(bio_channels)
            print(f"Debug - Channels from bio: {bio_channels}")
        
        # Check if user's username is itself a channel
        if user.username:
            try:
                channel_entity = await client.get_entity(user.username)
                from telethon import types
                if isinstance(channel_entity, types.Channel):
                    channels.add(user.username)
                    print(f"Debug - Added user's username as channel: {user.username}")
            except Exception as e:
                print(f"Debug - Username channel check failed: {str(e)}")
                
            # Try alternative method: check if a channel exists with the same name
            try:
                from telethon.tl.functions.contacts import ResolveUsernameRequest
                result = await client(ResolveUsernameRequest(user.username))
                if result and hasattr(result, 'peer') and isinstance(result.peer, types.PeerChannel):
                    channels.add(user.username)
                    print(f"Debug - Added user's username as channel via ResolveUsernameRequest: {user.username}")
            except Exception as e:
                print(f"Debug - ResolveUsernameRequest failed: {str(e)}")
        
        # Check for channel in the chats array from the API response
        if hasattr(full_user_result, 'chats') and full_user_result.chats:
            for chat in full_user_result.chats:
                if hasattr(chat, 'username') and chat.username:
                    channels.add(chat.username)
                    print(f"Debug - Added channel from chats array: {chat.username}")
                    
        # CRITICAL FIX 4: Get additional chat info from API response
        if hasattr(full_user_result, 'users') and full_user_result.users:
            print(f"Debug - Found {len(full_user_result.users)} users in API response")
            for user_info in full_user_result.users:
                if hasattr(user_info, 'username') and user_info.username:
                    print(f"Debug - Checking additional user: {user_info.username}")
                    try:
                        channel_entity = await client.get_entity(user_info.username)
                        if isinstance(channel_entity, types.Channel):
                            channels.add(user_info.username)
                            print(f"Debug - Added channel from users array: {user_info.username}")
                    except Exception as e:
                        print(f"Debug - Failed to check user from users array: {str(e)}")
        
        print(f"Debug - Final channels found for {user_input}: {channels}")
        
    except Exception as e:
        print(f"Error processing user {user_input}: {str(e)}")
    
    return channels

async def try_direct_fetch_user_channel(client, username):
    """Try a direct method to fetch a user's channel by using alternative API endpoints"""
    channels = set()
    
    try:
        # Method 1: Try to get the channel directly from username
        from telethon.tl.functions.channels import JoinChannelRequest
        try:
            # Just checking if the entity exists as a channel
            channel = await client.get_entity(username)
            from telethon import types
            if isinstance(channel, types.Channel):
                channels.add(username)
                print(f"Debug - Direct check found channel: {username}")
        except Exception as e:
            print(f"Debug - Direct channel check failed: {str(e)}")
        
        # Method 2: Try alternative username formats
        variations = [
            username,                  # original
            f"{username}_channel",     # common pattern
            f"{username}channel",      # no underscore
            f"channel_{username}",     # prefix
            f"ch_{username}"           # short prefix
        ]
        
        for variation in variations:
            try:
                channel = await client.get_entity(variation)
                if hasattr(channel, 'username') and channel.username:
                    channels.add(channel.username)
                    print(f"Debug - Found channel via name variation: {channel.username}")
            except Exception:
                continue
    
    except Exception as e:
        print(f"Debug - Alternative channel lookup methods failed: {str(e)}")
    
    return channels

async def main():
    # Initialize client
    client = TelegramClient('session_name', API_ID, API_HASH)
    await client.start()
    
    # Read accounts from file
    with open('accounts.txt', 'r') as f:
        accounts = [line.strip() for line in f.readlines()]
    
    # Process each account
    all_channels = set()
    for account in accounts:
        if account:
            print(f"\nProcessing account: {account}")
            
            # Process with normal method
            channels = await process_user(client, account)
            all_channels.update(channels)
            
            # If no channels found, try direct method as fallback
            if not channels and account.startswith('@'):
                print(f"Debug - No channels found with primary method, trying alternative methods...")
                username = account[1:]  # Remove @ symbol
                direct_channels = await try_direct_fetch_user_channel(client, username)
                all_channels.update(direct_channels)
                
                if direct_channels:
                    print(f"Debug - Alternative methods found channels: {direct_channels}")
                else:
                    print(f"Debug - Alternative methods also failed to find channels")
    
    # Save results
    with open('channels.txt', 'w') as f:
        for channel in sorted(all_channels):
            f.write(f"{channel}\n")
    
    print(f"\nExtracted {len(all_channels)} unique channels and saved to channels.txt")
    await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())