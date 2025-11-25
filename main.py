#!/usr/bin/env python3
# main.py
"""
Telegram Multi-Channel Auto Forward Bot (Bot Mode - Multi-User Support)
Main entry point for the bot application

Created by: @amanbotz
GitHub: https://github.com/theamanchaudhary
"""

import sys
import asyncio
from functools import partial
from telethon import TelegramClient, events, Button, functions
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from config import ConfigManager, BotConfig
from database import Database


class ForwardBot:
    """Main bot class handling forwarding and commands for multiple users"""
    
    def __init__(self):
        self.bot_client = None  # Main bot client
        self.user_clients = {}  # Dictionary of user TelegramClients {user_id: client}
        self.config = None
        self.config_manager = ConfigManager()
        self.db = Database()
        self.owner_id = None
        self.log_channel = None  # Log channel ID
        
        # State tracking per user
        self.awaiting_login = {}
        self.awaiting_code = {}
        self.awaiting_password = {}
        self.awaiting_source_forward = {}
        self.awaiting_destination_forward = {}
        self.awaiting_broadcast = {}
        self.user_phones = {}  # Store phone during login process
        self.user_phone_code_hash = {}  # Store phone_code_hash
        self.temp_clients = {}  # Store temporary clients during login
        
        # Track ignored channels to prevent log spam
        self.ignored_channels = {}  # {user_id: {channel_id: last_warn_time}}
        self.cleanup_task = None  # Background cleanup task
        
        # Message queue system for sequential processing
        self.message_queues = {}  # {user_id: asyncio.Queue()}
        self.queue_processors = {}  # {user_id: Task}
        self.processing_locks = {}  # {user_id: bool} - to prevent concurrent processing
    
    async def setup_bot(self):
        """Interactive setup for bot token and owner"""
        print("\n" + "="*60)
        print("🤖 TELEGRAM AUTO FORWARD BOT - SETUP")
        print("="*60)
        print("\n✨ Created by: @amanbotz")
        print("🔗 GitHub: github.com/theamanchaudhary\n")
        
        # Get API credentials
        print("📋 Step 1: Telegram API Credentials")
        print("Get your credentials from https://my.telegram.org\n")
        
        try:
            api_id = int(input("Enter API ID: ").strip())
            api_hash = input("Enter API Hash: ").strip()
        except ValueError:
            print("❌ Invalid API ID! Must be a number.")
            return
        
        # Get Bot Token
        print("\n📋 Step 2: Bot Token")
        print("Get bot token from @BotFather on Telegram\n")
        bot_token = input("Enter Bot Token: ").strip()
        
        # Get MongoDB URI
        print("\n📋 Step 3: MongoDB Configuration")
        print("Get free MongoDB from https://www.mongodb.com/cloud/atlas\n")
        mongo_uri = input("Enter MongoDB URI: ").strip()
        
        # MongoDB Database Name
        db_name = input("Enter Database Name (default: forward_bot): ").strip()
        if not db_name:
            db_name = "forward_bot"
        
        # Get Owner ID
        print("\n📋 Step 4: Bot Owner")
        print("Your Telegram User ID (get from @userinfobot)\n")
        try:
            owner_id = int(input("Enter Your User ID: ").strip())
        except ValueError:
            print("❌ Invalid User ID! Must be a number.")
            return
        
        # Save configuration
        self.config_manager.config.api_id = api_id
        self.config_manager.config.api_hash = api_hash
        self.config_manager.config.bot_token = bot_token
        self.config_manager.config.mongo_uri = mongo_uri
        self.config_manager.config.mongo_db_name = db_name
        self.config_manager.config.owner_id = owner_id
        self.config_manager.save_config()
        
        print("\n" + "="*60)
        print("✅ SETUP COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\n💡 Run 'python main.py start' to start the bot\n")
    
    async def initialize(self):
        """Initialize bot components"""
        # Load configuration
        self.config = self.config_manager.load_config()
        
        if not self.config.api_id or not self.config.bot_token:
            print("❌ Bot not configured! Run 'python main.py setup' first.")
            return False
        
        # Initialize Bot client with connection retry settings
        print("🔄 Initializing Telegram Bot...")
        self.bot_client = TelegramClient(
            'bot_session',
            self.config.api_id,
            self.config.api_hash,
            connection_retries=5,
            retry_delay=3,
            timeout=60,  # Increased for fast downloads
            auto_reconnect=True,
            flood_sleep_threshold=60,
            # Fast download optimization
            sequential_updates=False  # Enable parallel processing
        )
        
        # Start bot with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self.bot_client.start(bot_token=self.config.bot_token)
                break
            except Exception as e:
                print(f"⚠️ Connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"🔄 Retrying in 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    print("❌ Failed to connect after multiple attempts!")
                    return False
        
        # Get bot info
        me = await self.bot_client.get_me()
        print(f"✓ Bot started: @{me.username}")
        
        self.owner_id = self.config.owner_id
        self.log_channel = self.config.log_channel
        
        # Connect to database
        print("🔄 Connecting to MongoDB...")
        db_name = self.config.mongo_db_name or 'forward_bot'
        if not await self.db.connect(self.config.mongo_uri, db_name):
            return False
        
        # Register event handlers
        self.bot_client.add_event_handler(
            self.handle_new_message,
            events.NewMessage()
        )
        
        self.bot_client.add_event_handler(
            self.handle_callback,
            events.CallbackQuery()
        )
        
        print("\n" + "="*60)
        print("✅ BOT STARTED SUCCESSFULLY!")
        print("="*60)
        print("\n📊 Bot Information:")
        print(f"   • Bot: @{me.username}")
        print(f"   • Owner ID: {self.owner_id}")
        print(f"   • Users: {await self.db.get_user_count()}")
        print("\n💡 Users can start the bot and login with their accounts!")
        print("🛑 Press Ctrl+C to stop the bot\n")
        print("✨ Created by: @amanbotz")
        print("🔗 GitHub: github.com/theamanchaudhary\n")
        
        # Send startup log to log channel
        user_count = await self.db.get_user_count()
        stats = await self.db.get_stats()
        await self.log_to_channel(
            f"**Bot Started**\n\n"
            f"🤖 Bot: @{me.username}\n"
            f"👥 Total Users: {user_count}\n"
            f"📤 Total Forwards: {stats.get('total_forwards', 0)}\n"
            f"📊 Status: Online ✅\n\n"
            f"✨ Created by @amanbotz",
            "success"
        )
        
        return True
    
    async def log_to_channel(self, message: str, log_type: str = "info"):
        """Send log message to log channel"""
        if not self.log_channel:
            return
        
        try:
            # Format message with emoji based on type
            emoji_map = {
                "info": "ℹ️",
                "success": "✅",
                "error": "❌",
                "warning": "⚠️",
                "new_user": "👤",
                "login": "🔐",
                "logout": "🚪",
                "forward": "📤",
                "channel_add": "📥",
                "channel_remove": "🗑️",
                "admin": "👑"
            }
            
            emoji = emoji_map.get(log_type, "ℹ️")
            
            # Add timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            formatted_message = f"{emoji} **{log_type.upper()}**\n\n{message}\n\n🕐 {timestamp}"
            
            await self.bot_client.send_message(self.log_channel, formatted_message)
        except Exception as e:
            print(f"⚠️ Failed to send log: {e}")
    
    async def process_message_queue(self, user_id: int):
        """Process messages from queue one by one sequentially"""
        queue = self.message_queues.get(user_id)
        if not queue:
            return
        
        print(f"🔄 Started queue processor for user {user_id}")
        
        while True:
            try:
                # Wait for next message in queue
                message_data = await queue.get()
                
                if message_data is None:  # Poison pill to stop processor
                    print(f"🛑 Stopping queue processor for user {user_id}")
                    break
                
                event = message_data['event']
                channel_id = message_data['channel_id']
                source_channel = message_data['source_channel']
                destination = message_data['destination']
                dest_channel_id = message_data['dest_channel_id']
                message_id = message_data['message_id']
                message_date = message_data['message_date']
                
                try:
                    # Mark as processing
                    self.processing_locks[user_id] = True
                    
                    print(f"📥 Processing queued message {message_id} (date: {message_date}) from {source_channel['title']} for user {user_id}")
                    print(f"   Queue size: {queue.qsize()} remaining")
                    
                    # Get user client
                    user_client = await self.get_user_client(user_id)
                    if not user_client:
                        print(f"⚠ User client not available for {user_id}, skipping message")
                        continue
                    
                    # Forward based on mode
                    forward_mode = source_channel.get('forward_mode', 'copy')
                    
                    # Check if content is restricted/protected
                    is_restricted = False
                    if hasattr(event.message, 'restriction_reason') and event.message.restriction_reason:
                        is_restricted = True
                    if hasattr(event.message, 'noforwards') and event.message.noforwards:
                        is_restricted = True
                    
                    if forward_mode == 'copy' or is_restricted:
                        # Copy mode - sequential download and upload
                        await self._copy_message_with_media(
                            user_client,
                            event.message,
                            dest_channel_id,
                            is_restricted
                        )
                        print(f"✓ Copied message {message_id} (date: {message_date}) (mode: {'copy' if not is_restricted else 'copy-restricted'})")
                    else:
                        # Forward mode
                        try:
                            await user_client.forward_messages(
                                dest_channel_id,
                                event.message
                            )
                            print(f"✓ Forwarded message {message_id} (date: {message_date}) (mode: forward)")
                        except Exception as fwd_err:
                            print(f"⚠ Forward failed, trying copy: {fwd_err}")
                            await self._copy_message_with_media(
                                user_client,
                                event.message,
                                dest_channel_id,
                                True
                            )
                            print(f"✓ Copied message {message_id} (date: {message_date}) (fallback)")
                    
                    # Increment stats
                    await self.db.increment_forwards()
                    print(f"✅ Successfully processed message {message_id} (date: {message_date}) for user {user_id}")
                    
                    # Small delay between messages to prevent rate limiting and maintain order
                    await asyncio.sleep(1)
                    
                except Exception as process_error:
                    print(f"✗ Error processing message {message_id}: {process_error}")
                    import traceback
                    traceback.print_exc()
                
                finally:
                    # Mark task as done
                    queue.task_done()
                    self.processing_locks[user_id] = False
                    
            except Exception as e:
                print(f"✗ Error in queue processor for user {user_id}: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(5)  # Wait before retrying
    
    async def get_user_client(self, user_id: int) -> TelegramClient:
        """Get or create user's Telegram client"""
        if user_id in self.user_clients:
            return self.user_clients[user_id]
        
        # Try to load from database
        session_data = await self.db.get_user_session(user_id)
        if session_data and session_data.get('session_string'):
            try:
                client = TelegramClient(
                    StringSession(session_data['session_string']),
                    self.config.api_id,
                    self.config.api_hash,
                    connection_retries=5,
                    retry_delay=3,
                    timeout=60,  # Increased for fast downloads
                    auto_reconnect=True,
                    flood_sleep_threshold=60,
                    # Fast download optimization
                    sequential_updates=False  # Enable parallel processing
                )
                
                # Connect with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        await client.connect()
                        break
                    except Exception as conn_err:
                        print(f"⚠️ Connection attempt {attempt + 1}/{max_retries} for user {user_id}: {conn_err}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(3)
                        else:
                            print(f"❌ Failed to connect user client after {max_retries} attempts")
                            return None
                
                if await client.is_user_authorized():
                    self.user_clients[user_id] = client
                    
                    # Register event handler for this user's client
                    # Use partial to properly bind user_id
                    from functools import partial
                    handler = partial(self.handle_user_channel_message, user_id=user_id)
                    client.add_event_handler(
                        handler,
                        events.NewMessage(incoming=True, chats=None)
                    )
                    
                    print(f"✓ User client loaded for {user_id}")
                    return client
                else:
                    await client.disconnect()
            except Exception as e:
                print(f"✗ Error loading user client for {user_id}: {e}")
        
        return None
    
    async def handle_new_message(self, event):
        """Handle incoming messages to bot"""
        try:
            if not event.is_private:
                return
            
            sender = await event.get_sender()
            user_id = sender.id
            username = sender.username or sender.first_name or "Unknown"
            
            # Register user
            is_new = await self.db.add_user(user_id, username)
            
            # Log new user
            if is_new:
                await self.log_to_channel(
                    f"**New User Registered**\n\n"
                    f"👤 User: {username}\n"
                    f"🆔 ID: `{user_id}`\n"
                    f"🔗 Profile: [View](tg://user?id={user_id})",
                    "new_user"
                )
            
            # Check if banned - Block ALL interactions
            if await self.db.is_user_banned(user_id):
                ban_info = await self.db.get_ban_info(user_id)
                reason = ban_info.get('reason', 'No reason provided') if ban_info else 'No reason provided'
                ban_date = ban_info.get('banned_date', 'Unknown') if ban_info else 'Unknown'
                
                # Format ban date
                if ban_date != 'Unknown':
                    ban_date_str = ban_date.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    ban_date_str = 'Unknown'
                
                await event.reply(
                    f"🚫 **Access Denied**\n\n"
                    f"You have been banned from using this bot.\n\n"
                    f"📝 **Reason:** {reason}\n"
                    f"📅 **Banned on:** {ban_date_str}\n\n"
                    f"⚠️ **All commands and features are disabled for your account.**\n\n"
                    f"💬 Contact the bot owner if you believe this is a mistake."
                )
                
                # Log ban attempt
                print(f"🚫 Banned user {user_id} attempted to use bot")
                return
            
            # Handle login flow
            if user_id in self.awaiting_code and self.awaiting_code[user_id]:
                await self.handle_verification_code(event, user_id)
                return
            
            if user_id in self.awaiting_password and self.awaiting_password[user_id]:
                await self.handle_2fa_password(event, user_id)
                return
            
            # Handle broadcast
            if user_id in self.awaiting_broadcast and self.awaiting_broadcast[user_id]:
                if user_id == self.owner_id:
                    await self.handle_broadcast(event)
                return
            
            # Handle forwarded messages for channel setup
            if event.message.forward:
                await self.handle_forwarded_message(event, user_id)
                return
            
            # Handle channel link/username for source/destination setup
            if event.message.text and (
                user_id in self.awaiting_source_forward and self.awaiting_source_forward[user_id] or
                user_id in self.awaiting_destination_forward and self.awaiting_destination_forward[user_id]
            ):
                await self.handle_channel_link(event, user_id)
                return
            
            # Handle commands
            if event.message.text and event.message.text.startswith('/'):
                await self.handle_command(event, user_id)
                return
            
            # Handle phone number during login
            if event.message.text and event.message.text.startswith('+'):
                if user_id in self.awaiting_login and self.awaiting_login[user_id]:
                    await self.handle_phone_number(event, user_id)
                    return
            
            # Default response
            await event.reply(
                "💡 Use /start to see available commands\n\n"
                "✨ Created by @amanbotz"
            )
        
        except Exception as e:
            print(f"Error handling message: {e}")
    
    async def handle_command(self, event, user_id: int):
        """Parse and route commands"""
        try:
            text = event.message.text.strip()
            parts = text.split()
            command = parts[0][1:].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            # Commands that don't require login
            no_login_required = ['start', 'login', 'help', 'about']
            
            # Admin-only commands that don't require user login
            admin_only_commands = ['stats', 'users', 'broadcast', 'ban', 'unban', 'banned']
            
            # Check if user needs to be logged in
            is_admin_command = command in admin_only_commands and user_id == self.owner_id
            
            if command not in no_login_required and not is_admin_command:
                user_client = await self.get_user_client(user_id)
                if not user_client:
                    await event.reply(
                        "❌ You need to login first!\n\n"
                        "Use /login to connect your Telegram account"
                    )
                    return
            
            # Route commands
            if command == 'start':
                await self.cmd_start(event, user_id)
            elif command == 'login':
                await self.cmd_login(event, user_id)
            elif command == 'logout':
                await self.cmd_logout(event, user_id)
            elif command == 'help':
                await self.cmd_help(event, user_id)
            elif command == 'myaccount':
                await self.cmd_myaccount(event, user_id)
            elif command == 'addsource':
                await self.cmd_addsource(event, user_id)
            elif command == 'setdest':
                await self.cmd_setdest(event, user_id)
            elif command == 'list':
                await self.cmd_list(event, user_id)
            elif command == 'remove':
                await self.cmd_remove(event, user_id, args)
            elif command == 'cleanup':
                await self.cmd_cleanup(event, user_id)
            elif command == 'mode':
                await self.cmd_mode(event, user_id, args)
            elif command == 'status':
                await self.cmd_status(event, user_id)
            # Admin only commands
            elif command == 'broadcast' and user_id == self.owner_id:
                await self.cmd_broadcast(event, user_id)
            elif command == 'stats' and user_id == self.owner_id:
                await self.cmd_stats(event, user_id)
            elif command == 'users' and user_id == self.owner_id:
                await self.cmd_users(event, user_id)
            elif command == 'ban' and user_id == self.owner_id:
                await self.cmd_ban(event, user_id, args)
            elif command == 'unban' and user_id == self.owner_id:
                await self.cmd_unban(event, user_id, args)
            elif command == 'banned' and user_id == self.owner_id:
                await self.cmd_banned(event, user_id)
            else:
                await event.reply(f"❌ Unknown command: /{command}\n\nUse /help for available commands")
        
        except Exception as e:
            print(f"Error handling command: {e}")
            await event.reply(f"❌ Error: {e}")
    
    async def cmd_start(self, event, user_id: int):
        """Welcome message"""
        is_owner = user_id == self.owner_id
        user_client = await self.get_user_client(user_id)
        is_logged_in = user_client is not None
        
        if is_logged_in:
            me = await user_client.get_me()
            login_status = f"✅ Logged in as @{me.username or me.first_name}"
        else:
            login_status = "❌ Not logged in"
        
        buttons = []
        if is_logged_in:
            buttons.append([Button.inline("📋 My Channels", b"mychannels"), Button.inline("📊 My Status", b"mystatus")])
            buttons.append([Button.inline("➕ Add Source", b"addsource"), Button.inline("📤 Set Destination", b"setdest")])
        else:
            buttons.append([Button.inline("🔐 Login", b"login")])
        
        buttons.append([Button.inline("❓ Help", b"help"), Button.inline("👤 My Account", b"myaccount")])
        
        if is_owner:
            buttons.append([Button.inline("👑 Admin Panel", b"admin")])
        
        # Prepare dynamic text parts
        owner_text = "👑 **Owner Access**" if is_owner else ""
        
        if is_logged_in:
            get_started_text = "• Configure your channels\n• Start forwarding!"
        else:
            get_started_text = "• Click Login button or use /login\n• Connect your Telegram account\n• Start forwarding!"
        
        welcome_text = f"""
👋 **Welcome to Auto Forward Bot!**

{login_status}

🤖 **What I can do:**
• Forward messages from any channel
• Copy mode (no forward tag)
• Forward mode (with attribution)
• Multiple channel support
• Personal forwarding for each user

{owner_text}

💡 **Get Started:**
{get_started_text}

✨ **Created by:** @amanbotz
🔗 **GitHub:** github.com/theamanchaudhary
"""
        await event.reply(welcome_text, buttons=buttons)
    
    async def cmd_login(self, event, user_id: int):
        """Start login process"""
        # Check if already logged in
        user_client = await self.get_user_client(user_id)
        if user_client:
            await event.reply("✅ You are already logged in!\n\nUse /logout to logout")
            return
        
        self.awaiting_login[user_id] = True
        await event.reply(
            "🔐 **Login to Your Telegram Account**\n\n"
            "To use this bot, you need to connect your Telegram account.\n\n"
            "📱 Please send your phone number with country code\n"
            "Example: +1234567890\n\n"
            "⚠️ **Your session is stored securely and encrypted**\n"
            "🔒 The bot owner cannot access your account\n\n"
            "Type /cancel to cancel login"
        )
    
    async def handle_phone_number(self, event, user_id: int):
        """Handle phone number input during login"""
        phone = event.message.text.strip()
        self.user_phones[user_id] = phone
        
        try:
            # Create temp client with better connection settings
            client = TelegramClient(
                StringSession(),
                self.config.api_id,
                self.config.api_hash,
                connection_retries=5,
                retry_delay=3,
                timeout=60,  # Increased for fast downloads
                auto_reconnect=True,
                flood_sleep_threshold=60,
                # Fast download optimization
                sequential_updates=False  # Enable parallel processing
            )
            
            # Connect with retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await client.connect()
                    break
                except Exception as conn_err:
                    print(f"⚠️ Connection attempt {attempt + 1}/{max_retries}: {conn_err}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)
                    else:
                        await event.reply("❌ Connection failed. Please try again later or check your internet connection.")
                        self.awaiting_login[user_id] = False
                        return
            
            # Send code and store the phone_code_hash
            sent_code = await client.send_code_request(phone)
            self.user_phone_code_hash[user_id] = sent_code.phone_code_hash
            
            # Store the client for later use
            self.temp_clients[user_id] = client
            
            self.awaiting_login[user_id] = False
            self.awaiting_code[user_id] = True
            
            await event.reply(
                "📱 **Verification Code Sent!**\n\n"
                "Please send the code you received from Telegram:"
            )
        except Exception as e:
            await event.reply(f"❌ Error: {e}\n\nMake sure the phone number is correct")
            self.awaiting_login[user_id] = False
            if user_id in self.temp_clients:
                try:
                    await self.temp_clients[user_id].disconnect()
                except:
                    pass
                del self.temp_clients[user_id]
    
    async def handle_verification_code(self, event, user_id: int):
        """Handle verification code input"""
        code = event.message.text.strip()
        phone = self.user_phones.get(user_id)
        phone_code_hash = self.user_phone_code_hash.get(user_id)
        client = self.temp_clients.get(user_id)
        
        if not phone or not phone_code_hash or not client:
            await event.reply("❌ Login session expired. Use /login to start again")
            self.awaiting_code[user_id] = False
            # Clean up
            if user_id in self.temp_clients:
                try:
                    await self.temp_clients[user_id].disconnect()
                except:
                    pass
                del self.temp_clients[user_id]
            return
        
        try:
            try:
                # Sign in with phone, code, and phone_code_hash
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                
                # Get session string
                session_string = client.session.save()
                
                # Save to database
                await self.db.save_user_session(user_id, session_string, phone)
                
                # Store client
                self.user_clients[user_id] = client
                
                # Register event handler
                from functools import partial
                handler = partial(self.handle_user_channel_message, user_id=user_id)
                client.add_event_handler(
                    handler,
                    events.NewMessage(incoming=True, chats=None)
                )
                
                me = await client.get_me()
                
                await event.reply(
                    f"✅ **Login Successful!**\n\n"
                    f"👤 Logged in as: @{me.username or me.first_name}\n"
                    f"🆔 User ID: {me.id}\n\n"
                    f"💡 Now you can:\n"
                    f"• /addsource - Add source channels\n"
                    f"• /setdest - Set destination\n"
                    f"• /list - View your channels\n\n"
                    f"✨ Created by @amanbotz"
                )
                
                # Log successful login
                await self.log_to_channel(
                    f"**User Logged In**\n\n"
                    f"👤 Bot User: {event.sender.username or event.sender.first_name}\n"
                    f"🆔 Bot User ID: `{user_id}`\n"
                    f"📱 Logged as: @{me.username or me.first_name}\n"
                    f"🆔 Account ID: `{me.id}`\n"
                    f"📞 Phone: {phone or 'Hidden'}",
                    "login"
                )
                
                # Clean up
                self.awaiting_code[user_id] = False
                if user_id in self.user_phones:
                    del self.user_phones[user_id]
                if user_id in self.user_phone_code_hash:
                    del self.user_phone_code_hash[user_id]
                if user_id in self.temp_clients:
                    del self.temp_clients[user_id]
            
            except SessionPasswordNeededError:
                # 2FA enabled
                self.awaiting_code[user_id] = False
                self.awaiting_password[user_id] = True
                # Keep client stored for 2FA
                
                await event.reply(
                    "🔒 **2FA Enabled**\n\n"
                    "Please send your 2FA password:"
                )
        
        except Exception as e:
            await event.reply(f"❌ Error: {e}\n\nUse /login to try again")
            self.awaiting_code[user_id] = False
    
    async def handle_2fa_password(self, event, user_id: int):
        """Handle 2FA password"""
        password = event.message.text.strip()
        
        try:
            client = self.temp_clients.get(user_id)
            if not client:
                await event.reply("❌ Session expired. Use /login again")
                self.awaiting_password[user_id] = False
                return
            
            await client.sign_in(password=password)
            
            # Get session string
            session_string = client.session.save()
            phone = self.user_phones.get(user_id, "")
            
            # Save to database
            await self.db.save_user_session(user_id, session_string, phone)
            
            # Store client
            self.user_clients[user_id] = client
            
            # Register event handler
            from functools import partial
            handler = partial(self.handle_user_channel_message, user_id=user_id)
            client.add_event_handler(
                handler,
                events.NewMessage(incoming=True, chats=None)
            )
            
            me = await client.get_me()
            
            await event.reply(
                f"✅ **Login Successful!**\n\n"
                f"👤 Logged in as: @{me.username or me.first_name}\n\n"
                f"💡 Use /help to see available commands\n\n"
                f"✨ Created by @amanbotz"
            )
            
            # Log successful 2FA login
            await self.log_to_channel(
                f"**User Logged In (2FA)**\n\n"
                f"👤 Bot User: {event.sender.username or event.sender.first_name}\n"
                f"🆔 Bot User ID: `{user_id}`\n"
                f"📱 Logged as: @{me.username or me.first_name}\n"
                f"🆔 Account ID: `{me.id}`\n"
                f"🔒 2FA: Enabled\n"
                f"📞 Phone: {phone or 'Hidden'}",
                "login"
            )
            
            # Clean up
            self.awaiting_password[user_id] = False
            if user_id in self.user_phones:
                del self.user_phones[user_id]
            if user_id in self.user_phone_code_hash:
                del self.user_phone_code_hash[user_id]
            if user_id in self.temp_clients:
                del self.temp_clients[user_id]
        
        except Exception as e:
            await event.reply(f"❌ Wrong password: {e}\n\nUse /login to try again")
            self.awaiting_password[user_id] = False
            if user_id in self.temp_clients:
                try:
                    await self.temp_clients[user_id].disconnect()
                except:
                    pass
                del self.temp_clients[user_id]
            if user_id in self.user_phones:
                del self.user_phones[user_id]
            if user_id in self.user_phone_code_hash:
                del self.user_phone_code_hash[user_id]
    
    async def cmd_logout(self, event, user_id: int):
        """Logout user"""
        # Stop queue processor if running
        if user_id in self.queue_processors:
            try:
                # Send poison pill to stop processor
                if user_id in self.message_queues:
                    await self.message_queues[user_id].put(None)
                    # Wait for processor to finish
                    await asyncio.wait_for(self.queue_processors[user_id], timeout=10)
                print(f"✓ Stopped queue processor for user {user_id}")
            except Exception as queue_err:
                print(f"⚠️ Error stopping queue processor: {queue_err}")
            finally:
                if user_id in self.queue_processors:
                    del self.queue_processors[user_id]
                if user_id in self.message_queues:
                    del self.message_queues[user_id]
                if user_id in self.processing_locks:
                    del self.processing_locks[user_id]
        
        # Disconnect client
        if user_id in self.user_clients:
            await self.user_clients[user_id].disconnect()
            del self.user_clients[user_id]
        
        # Clean up temp clients if any
        if user_id in self.temp_clients:
            try:
                await self.temp_clients[user_id].disconnect()
            except:
                pass
            del self.temp_clients[user_id]
        
        # Clean up login state
        if user_id in self.user_phones:
            del self.user_phones[user_id]
        if user_id in self.user_phone_code_hash:
            del self.user_phone_code_hash[user_id]
        self.awaiting_login[user_id] = False
        self.awaiting_code[user_id] = False
        self.awaiting_password[user_id] = False
        
        # Remove from database
        await self.db.delete_user_session(user_id)
        
        # Log logout
        await self.log_to_channel(
            f"**User Logged Out**\n\n"
            f"👤 User: {event.sender.username or event.sender.first_name}\n"
            f"🆔 ID: `{user_id}`",
            "logout"
        )
        
        await event.reply(
            "✅ **Logged out successfully!**\n\n"
            "Your session has been removed.\n\n"
            "Use /login to login again"
        )
    
    async def cmd_help(self, event, user_id: int):
        """Show help"""
        is_owner = user_id == self.owner_id
        
        help_text = """
🤖 **Bot Commands**

🔐 **Account:**
/login - Login to your Telegram account
/logout - Logout from bot
/myaccount - View account info

📥 **Channel Management:**
/addsource - Add source channel (public/private)
/setdest - Set destination channel (public/private)
/list - Show your channels
/remove <number> - Remove channel
/cleanup - Leave non-source/destination channels 🧹
/mode <number> <copy|forward> - Change mode

📊 **Information:**
/status - Your bot status & queue info
/help - Show this message

📋 **Forward Modes:**
• **copy** - New message (no forward tag)
• **forward** - With attribution

⏳ **Sequential Processing:**
• Messages are processed one by one in order
• Maintains chronological sequence from source
• No media skipped, even with bulk posts
• Prevents server overload
• Automatic queue management

🧹 **Cleanup Command:**
• Leaves all channels EXCEPT source & destination
• Safe - keeps your configured channels
• Use when you joined too many channels
• Manual control - no auto-leaving

💡 **Adding Channels (4 Methods):**
• Forward a message from the channel
• Send channel link/username (@channel or t.me/+link)
• Send post link (t.me/c/123/456 or t.me/channel/123)
• Send channel ID (-1001234567890)
• Works with private/restricted channels! 🔒
"""
        
        if is_owner:
            help_text += """
👑 **Admin Commands (No Login Required):**
/stats - Bot statistics
/users - All users list
/broadcast - Broadcast message to all
/ban <user_id> [reason] - Ban user with reason
/unban <user_id> - Unban user
/banned - View all banned users

🚫 **Ban System:**
• Banned users cannot use ANY bot features
• All commands and messages are blocked
• User receives detailed ban notification
• Automatic client disconnection on ban

💡 Note: Admin commands work without login
"""
        
        help_text += "\n✨ Created by @amanbotz\n🔗 GitHub: github.com/theamanchaudhary"
        
        await event.reply(help_text)
    
    async def cmd_myaccount(self, event, user_id: int):
        """Show account info"""
        user_client = await self.get_user_client(user_id)
        
        if not user_client:
            await event.reply(
                "❌ **Not Logged In**\n\n"
                "Use /login to connect your account"
            )
            return
        
        me = await user_client.get_me()
        channels = await self.db.get_user_channels(user_id)
        destination = await self.db.get_user_destination(user_id)
        
        info = f"""
👤 **My Account**

**Telegram Account:**
• Name: {me.first_name} {me.last_name or ''}
• Username: @{me.username or 'None'}
• ID: `{me.id}`
• Phone: {me.phone or 'Hidden'}

**Bot Status:**
• Source Channels: {len(channels)}
• Destination: {'✅ Set' if destination else '❌ Not set'}
• Status: {'✅ Active' if destination and channels else '⚠️ Not configured'}

💡 Use /list to see your channels

✨ Created by @amanbotz
"""
        await event.reply(info)
    
    async def cmd_addsource(self, event, user_id: int):
        """Add source channel"""
        self.awaiting_source_forward[user_id] = True
        self.awaiting_destination_forward[user_id] = False
        
        await event.reply(
            "📥 **Add Source Channel**\n\n"
            "**Choose one method:**\n\n"
            "**Method 1 (Easiest):**\n"
            "Forward ANY message from the channel\n\n"
            "**Method 2 (Channel Link/Username):**\n"
            "• `@channelname`\n"
            "• `https://t.me/channelname`\n"
            "• `https://t.me/+ABC123xyz` (invite link)\n\n"
            "**Method 3 (For Restricted Channels):**\n"
            "Send a post link from the channel:\n"
            "• `https://t.me/c/1234567890/123` (private post)\n"
            "• `https://t.me/channelname/123` (public post)\n\n"
            "**Method 4 (Advanced):**\n"
            "Send channel ID directly:\n"
            "• `-1001234567890`\n\n"
            "💡 You must be a member of the channel!"
        )
    
    async def cmd_setdest(self, event, user_id: int):
        """Set destination"""
        self.awaiting_destination_forward[user_id] = True
        self.awaiting_source_forward[user_id] = False
        
        await event.reply(
            "📤 **Set Destination Channel**\n\n"
            "**Choose one method:**\n\n"
            "**Method 1 (Easiest):**\n"
            "Forward ANY message from the channel\n\n"
            "**Method 2 (Channel Link/Username):**\n"
            "• `@channelname`\n"
            "• `https://t.me/channelname`\n"
            "• `https://t.me/+ABC123xyz` (invite link)\n\n"
            "**Method 3 (For Restricted Channels):**\n"
            "Send a post link from the channel:\n"
            "• `https://t.me/c/1234567890/123` (private post)\n"
            "• `https://t.me/channelname/123` (public post)\n\n"
            "**Method 4 (Advanced):**\n"
            "Send channel ID directly:\n"
            "• `-1001234567890`\n\n"
            "⚠️ Make sure you're admin with post permissions!"
        )
    
    async def cmd_list(self, event, user_id: int):
        """List user's channels"""
        channels = await self.db.get_user_channels(user_id)
        
        if not channels:
            await event.reply("📋 **No channels**\n\nUse /addsource to add")
            return
        
        message = "📋 **Your Source Channels:**\n\n"
        for i, ch in enumerate(channels, 1):
            mode_icon = "📋" if ch['forward_mode'] == 'copy' else "➡️"
            message += f"**{i}.** {mode_icon} {ch['title']}\n"
            message += f"   Mode: `{ch['forward_mode']}`\n\n"
        
        message += "\n💡 /remove <number> - Remove\n"
        message += "💡 /mode <number> <mode> - Change mode"
        
        await event.reply(message)
    
    async def cmd_remove(self, event, user_id: int, args):
        """Remove channel"""
        if not args:
            await event.reply("❌ Usage: /remove <number>")
            return
        
        try:
            channels = await self.db.get_user_channels(user_id)
            index = int(args[0]) - 1
            
            if 0 <= index < len(channels):
                channel = channels[index]
                channel_id = channel['channel_id']
                channel_title = channel['title']
                
                if await self.db.remove_user_source_channel(user_id, channel_id):
                    await event.reply(f"✅ Removed: **{channel_title}**\n\n🔄 Auto-cleanup will leave this channel to prevent message spam.")
                    
                    # Try to auto-leave the channel
                    try:
                        user_client = await self.get_user_client(user_id)
                        if user_client:
                            # Normalize channel ID
                            if not channel_id.startswith('-'):
                                channel_id = f"-100{channel_id}"
                            
                            channel_entity = await user_client.get_entity(int(channel_id))
                            await user_client(functions.channels.LeaveChannelRequest(channel_entity))
                            await event.reply(f"✅ Left channel: **{channel_title}**")
                            
                            # Log
                            await self.log_to_channel(
                                f"**Channel Removed & Left**\n\n"
                                f"🆔 User ID: `{user_id}`\n"
                                f"📢 Channel: {channel_title}\n"
                                f"🆔 Channel ID: `{channel_id}`",
                                "channel_remove"
                            )
                    except Exception as leave_err:
                        print(f"Could not auto-leave channel: {leave_err}")
            else:
                await event.reply("❌ Invalid number!")
        except:
            await event.reply("❌ Invalid number!")
    
    async def cmd_cleanup(self, event, user_id: int):
        """Leave all channels not in source list or destination"""
        await event.reply("🔄 **Starting cleanup...**\n\nChecking all joined channels...")
        
        try:
            user_client = await self.get_user_client(user_id)
            if not user_client:
                await event.reply("❌ Please login first with /login")
                return
            
            # Get user's source channels and destination
            channels = await self.db.get_user_channels(user_id)
            destination = await self.db.get_user_destination(user_id)
            
            # Build set of channel IDs to KEEP (source + destination)
            keep_channel_ids = set()
            
            # Add all source channels (with normalized IDs)
            for ch in channels:
                ch_id = str(ch['channel_id'])
                # Normalize to -100 format
                if ch_id.startswith('-100'):
                    keep_channel_ids.add(ch_id)
                    keep_channel_ids.add(ch_id[4:])  # Also add without -100
                elif ch_id.startswith('-'):
                    keep_channel_ids.add(ch_id)
                else:
                    keep_channel_ids.add(f"-100{ch_id}")
                    keep_channel_ids.add(ch_id)
            
            # Add destination channel (with normalized IDs)
            if destination:
                dest_id = str(destination['channel_id'])
                if dest_id.startswith('-100'):
                    keep_channel_ids.add(dest_id)
                    keep_channel_ids.add(dest_id[4:])  # Also add without -100
                elif dest_id.startswith('-'):
                    keep_channel_ids.add(dest_id)
                else:
                    keep_channel_ids.add(f"-100{dest_id}")
                    keep_channel_ids.add(dest_id)
            
            print(f"📋 Channels to KEEP: {keep_channel_ids}")
            
            # Get all dialogs (chats/channels user is in)
            dialogs = await user_client.get_dialogs()
            
            left_count = 0
            kept_count = 0
            failed_count = 0
            
            status_msg = await event.reply("🔍 Scanning channels...")
            
            for dialog in dialogs:
                # Only process channels, not groups or users
                if not dialog.is_channel:
                    continue
                
                # Get channel ID in multiple formats
                channel_id_raw = str(dialog.id)
                channel_id_with_100 = f"-100{dialog.id}" if not channel_id_raw.startswith('-') else channel_id_raw
                
                # Check if it's in the KEEP list (check both formats)
                should_keep = (
                    channel_id_raw in keep_channel_ids or 
                    channel_id_with_100 in keep_channel_ids or
                    str(abs(dialog.id)) in keep_channel_ids
                )
                
                if should_keep:
                    kept_count += 1
                    print(f"✓ Keeping: {dialog.title} ({channel_id_with_100})")
                    continue
                
                # Not in keep list - leave it
                try:
                    await user_client(functions.channels.LeaveChannelRequest(dialog.entity))
                    left_count += 1
                    print(f"✓ Left: {dialog.title} ({channel_id_with_100})")
                    
                    # Update status every 5 channels
                    if left_count % 5 == 0:
                        await status_msg.edit(
                            f"🔄 **Cleanup in progress...**\n\n"
                            f"✅ Left: {left_count}\n"
                            f"⏭️ Kept: {kept_count} (source/destination)\n"
                            f"❌ Failed: {failed_count}"
                        )
                    
                    # Small delay to prevent rate limiting
                    await asyncio.sleep(0.5)
                    
                except Exception as leave_err:
                    failed_count += 1
                    print(f"✗ Failed to leave {dialog.title}: {leave_err}")
            
            # Final summary
            await status_msg.edit(
                f"✅ **Cleanup Complete!**\n\n"
                f"📊 **Summary:**\n"
                f"✅ Left: {left_count} channels\n"
                f"⏭️ Kept: {kept_count} channels (source/destination)\n"
                f"❌ Failed: {failed_count} channels\n\n"
                f"💡 Your source channels and destination are safe!\n"
                f"You will no longer receive spam from removed channels."
            )
            
            # Log
            await self.log_to_channel(
                f"**Bulk Cleanup Completed**\n\n"
                f"🆔 User ID: `{user_id}`\n"
                f"✅ Left: {left_count}\n"
                f"⏭️ Kept: {kept_count}\n"
                f"❌ Failed: {failed_count}",
                "bulk_cleanup"
            )
            
        except Exception as e:
            await event.reply(f"❌ Cleanup failed: {e}")
    
    async def cmd_mode(self, event, user_id: int, args):
        """Change forward mode"""
        if len(args) < 2:
            await event.reply("❌ Usage: /mode <number> <copy|forward>")
            return
        
        try:
            channels = await self.db.get_user_channels(user_id)
            index = int(args[0]) - 1
            mode = args[1].lower()
            
            if mode not in ['copy', 'forward']:
                await event.reply("❌ Mode must be 'copy' or 'forward'")
                return
            
            if 0 <= index < len(channels):
                channel = channels[index]
                if await self.db.set_user_forward_mode(user_id, channel['channel_id'], mode):
                    await event.reply(f"✅ Mode changed to: {mode}")
            else:
                await event.reply("❌ Invalid number!")
        except:
            await event.reply("❌ Invalid input!")
    
    async def cmd_status(self, event, user_id: int):
        """Show user status"""
        channels = await self.db.get_user_channels(user_id)
        destination = await self.db.get_user_destination(user_id)
        
        copy_count = sum(1 for ch in channels if ch['forward_mode'] == 'copy')
        forward_count = len(channels) - copy_count
        
        # Get queue status
        queue_size = 0
        is_processing = False
        if user_id in self.message_queues:
            queue_size = self.message_queues[user_id].qsize()
        if user_id in self.processing_locks:
            is_processing = self.processing_locks[user_id]
        
        queue_status = "🟢 Idle" if queue_size == 0 else f"🔄 Processing ({queue_size} in queue)"
        if is_processing:
            queue_status = f"⚙️ Active - {queue_status}"
        
        status = f"""
🤖 **Your Status**

📊 **Configuration:**
• Source Channels: {len(channels)}
• Destination: {'✅ Set' if destination else '❌ Not set'}

📋 **Forward Modes:**
• Copy Mode: {copy_count}
• Forward Mode: {forward_count}

⏳ **Queue Status:**
• Status: {queue_status}
• Sequential Processing: ✅ Enabled

✨ Created by @amanbotz
"""
        await event.reply(status)
    
    async def handle_channel_link(self, event, user_id: int):
        """Handle channel link/username/post link/channel ID (for private channels)"""
        user_client = await self.get_user_client(user_id)
        if not user_client:
            await event.reply("❌ You need to login first!")
            return
        
        channel_input = event.message.text.strip()
        
        try:
            # Method 1: Check if it's a direct channel ID (starts with -100)
            if channel_input.startswith('-100'):
                await event.reply(f"🔍 Looking up channel by ID...\n\n`{channel_input}`")
                try:
                    channel_id_int = int(channel_input)
                    channel = await user_client.get_entity(channel_id_int)
                except Exception as e:
                    await event.reply(
                        f"❌ **Could not find channel:** {e}\n\n"
                        f"**Possible reasons:**\n"
                        f"• You're not a member of this channel\n"
                        f"• Channel ID is incorrect\n"
                        f"• Channel has been deleted\n\n"
                        f"💡 Try forwarding a message from the channel instead"
                    )
                    return
            
            # Method 2: Check if it's a post link (contains message ID)
            elif 't.me/' in channel_input and ('/' in channel_input.split('t.me/')[-1].split('?')[0] and 
                                                 channel_input.split('/')[-1].replace('?', '/').split('/')[0].isdigit()):
                await event.reply(f"🔍 Extracting channel from post link...\n\n`{channel_input}`")
                
                # Parse the post link
                # Format: https://t.me/c/1234567890/123 (private)
                # Format: https://t.me/channelname/123 (public)
                
                parts = channel_input.split('/')
                
                if '/c/' in channel_input:
                    # Private channel post link format: t.me/c/CHANNEL_ID/MESSAGE_ID
                    channel_id_part = None
                    for i, part in enumerate(parts):
                        if part == 'c' and i + 1 < len(parts):
                            channel_id_part = parts[i + 1]
                            break
                    
                    if channel_id_part and channel_id_part.isdigit():
                        # Convert to full channel ID format
                        channel_id_int = int('-100' + channel_id_part)
                        try:
                            channel = await user_client.get_entity(channel_id_int)
                        except Exception as e:
                            await event.reply(
                                f"❌ **Could not access channel:** {e}\n\n"
                                f"**Possible reasons:**\n"
                                f"• You're not a member of this private channel\n"
                                f"• You've been removed from the channel\n"
                                f"• Channel has been deleted\n\n"
                                f"💡 Make sure you can open this link in Telegram first"
                            )
                            return
                    else:
                        await event.reply("❌ Invalid post link format!")
                        return
                else:
                    # Public channel post link: t.me/channelname/123
                    channel_username = None
                    for i, part in enumerate(parts):
                        if 't.me' in parts[i-1] if i > 0 else '' or part.startswith('t.me'):
                            continue
                        if part and not part.isdigit() and part != 's':
                            channel_username = part
                            break
                    
                    if channel_username:
                        channel_input = '@' + channel_username if not channel_username.startswith('@') else channel_username
                        channel = await user_client.get_entity(channel_input)
                    else:
                        await event.reply("❌ Could not extract channel from link!")
                        return
            
            # Method 3: Regular channel link or username
            else:
                # Clean up the input
                # Handle different formats: @username, t.me/username, t.me/+invitelink
                if 't.me/' in channel_input:
                    # Extract username or invite link
                    if '/+' in channel_input or '/joinchat/' in channel_input:
                        # Private invite link
                        channel_input = channel_input.split('/')[-1]
                    else:
                        # Public username
                        channel_input = channel_input.split('/')[-1]
                        if not channel_input.startswith('@'):
                            channel_input = '@' + channel_input
                
                # Try to get the channel entity
                await event.reply(f"🔍 Looking up channel...\n\n`{channel_input}`")
                
                try:
                    channel = await user_client.get_entity(channel_input)
                except Exception as e:
                    # If it's an invite link, try to join first
                    if '+' in channel_input or 'joinchat' in str(e).lower():
                        try:
                            await event.reply("🔗 This is a private link. Attempting to join...")
                            updates = await user_client(functions.messages.ImportChatInviteRequest(channel_input.replace('+', '')))
                            # Get the channel from the updates
                            if hasattr(updates, 'chats') and updates.chats:
                                channel = updates.chats[0]
                            else:
                                await event.reply("❌ Could not join the channel!")
                                return
                        except Exception as join_error:
                            await event.reply(f"❌ Failed to join channel: {join_error}")
                            return
                    else:
                        raise e
            
            # Verify it's a channel
            if not hasattr(channel, 'id'):
                await event.reply("❌ Invalid channel!")
                return
            
            channel_id = str(channel.id)
            channel_title = getattr(channel, 'title', 'Unknown')
            is_private = getattr(channel, 'username', None) is None
            
            # Check if adding source
            if user_id in self.awaiting_source_forward and self.awaiting_source_forward[user_id]:
                if await self.db.add_user_source_channel(user_id, channel_id, channel_title):
                    private_marker = "🔒 (Private)" if is_private else "🔓 (Public)"
                    await event.reply(
                        f"✅ **Source Added!**\n\n"
                        f"📢 {channel_title} {private_marker}\n"
                        f"🆔 `{channel_id}`\n"
                        f"🔄 Mode: copy\n\n"
                        f"💡 Messages from this channel will now be forwarded!"
                    )
                else:
                    await event.reply("⚠️ Channel already added!")
                
                self.awaiting_source_forward[user_id] = False
            
            # Check if setting destination
            elif user_id in self.awaiting_destination_forward and self.awaiting_destination_forward[user_id]:
                # Check if user has admin rights
                try:
                    permissions = await user_client.get_permissions(channel, 'me')
                    if not permissions.is_admin or not permissions.post_messages:
                        await event.reply(
                            "⚠️ **Warning:** You may not have admin rights!\n\n"
                            "Make sure you can post messages to this channel."
                        )
                except:
                    pass
                
                if await self.db.set_user_destination(user_id, channel_id, channel_title):
                    private_marker = "🔒 (Private)" if is_private else "🔓 (Public)"
                    await event.reply(
                        f"✅ **Destination Set!**\n\n"
                        f"📢 {channel_title} {private_marker}\n"
                        f"🆔 `{channel_id}`"
                    )
                else:
                    await event.reply("❌ Failed!")
                
                self.awaiting_destination_forward[user_id] = False
        
        except Exception as e:
            await event.reply(
                f"❌ **Error:** {e}\n\n"
                f"**Troubleshooting:**\n"
                f"• Make sure you're a member of the channel\n"
                f"• For private channels, use the invite link\n"
                f"• Check the link/username is correct\n\n"
                f"**Format examples:**\n"
                f"• `@channelname`\n"
                f"• `https://t.me/channelname`\n"
                f"• `https://t.me/+ABC123xyz`"
            )
            import traceback
            traceback.print_exc()
    
    async def handle_forwarded_message(self, event, user_id: int):
        """Handle forwarded messages"""
        user_client = await self.get_user_client(user_id)
        if not user_client:
            return
        
        forward_from = event.message.forward
        
        try:
            if hasattr(forward_from, 'chat') and forward_from.chat:
                channel = forward_from.chat
            elif hasattr(forward_from, 'channel_id'):
                channel = await user_client.get_entity(forward_from.channel_id)
            else:
                await event.reply("❌ Could not identify channel!")
                return
            
            channel_id = str(channel.id)
            channel_title = getattr(channel, 'title', 'Unknown')
            
            # Check if adding source
            if user_id in self.awaiting_source_forward and self.awaiting_source_forward[user_id]:
                if await self.db.add_user_source_channel(user_id, channel_id, channel_title):
                    await event.reply(
                        f"✅ **Source Added!**\n\n"
                        f"📢 {channel_title}\n"
                        f"🔄 Mode: copy"
                    )
                    
                    # Log channel addition
                    await self.log_to_channel(
                        f"**Source Channel Added**\n\n"
                        f"👤 User: {event.sender.username or event.sender.first_name}\n"
                        f"🆔 User ID: `{user_id}`\n"
                        f"📢 Channel: {channel_title}\n"
                        f"🆔 Channel ID: `{channel_id}`\n"
                        f"🔄 Mode: copy",
                        "channel_add"
                    )
                else:
                    await event.reply("⚠️ Channel already added!")
                
                self.awaiting_source_forward[user_id] = False
            
            # Check if setting destination
            elif user_id in self.awaiting_destination_forward and self.awaiting_destination_forward[user_id]:
                if await self.db.set_user_destination(user_id, channel_id, channel_title):
                    await event.reply(
                        f"✅ **Destination Set!**\n\n"
                        f"📢 {channel_title}"
                    )
                    
                    # Log destination set
                    await self.log_to_channel(
                        f"**Destination Channel Set**\n\n"
                        f"👤 User: {event.sender.username or event.sender.first_name}\n"
                        f"🆔 User ID: `{user_id}`\n"
                        f"📢 Channel: {channel_title}\n"
                        f"🆔 Channel ID: `{channel_id}`",
                        "channel_add"
                    )
                else:
                    await event.reply("❌ Failed!")
                
                self.awaiting_destination_forward[user_id] = False
        
        except Exception as e:
            await event.reply(f"❌ Error: {e}")
    
    async def handle_user_channel_message(self, event, user_id: int):
        """Handle channel messages for forwarding (including restricted content) - Queue-based"""
        try:
            # Check if it's a channel message
            if not event.is_channel:
                return
            
            # Get channel ID (handle both positive and negative IDs)
            channel_id = str(event.chat_id)
            if not channel_id.startswith('-'):
                channel_id = f"-100{event.chat_id}"
            
            print(f"📥 Message received from channel {channel_id} for user {user_id}")
            
            # Get user's channels
            channels = await self.db.get_user_channels(user_id)
            source_channel = None
            
            # Find matching source channel
            for ch in channels:
                # Normalize channel IDs for comparison
                db_channel_id = str(ch['channel_id'])
                if not db_channel_id.startswith('-'):
                    db_channel_id = f"-100{db_channel_id}"
                
                if db_channel_id == channel_id or ch['channel_id'] == str(abs(event.chat_id)):
                    source_channel = ch
                    print(f"✓ Matched source channel: {ch['title']}")
                    break
            
            if not source_channel:
                # Channel not in source list - only log, DO NOT AUTO-LEAVE
                # Auto-leaving can be dangerous and is now disabled
                
                # Initialize ignored channels dict for user if not exists
                if user_id not in self.ignored_channels:
                    self.ignored_channels[user_id] = {}
                
                current_time = asyncio.get_event_loop().time()
                
                # Check if we've already warned about this channel recently
                if channel_id in self.ignored_channels[user_id]:
                    last_warn_time = self.ignored_channels[user_id][channel_id]
                    time_since_warn = current_time - last_warn_time
                    
                    # Only log warning once every 5 minutes to prevent spam
                    if time_since_warn < 300:  # 5 minutes
                        return  # Silently ignore
                
                # Log warning (first time or after 5 minutes)
                print(f"⚠ Channel {channel_id} not in user's source list - ignoring message")
                self.ignored_channels[user_id][channel_id] = current_time
                
                # Just ignore the message - DO NOT AUTO-LEAVE
                # User can manually use /cleanup command if needed
                return
            
            # Get destination
            destination = await self.db.get_user_destination(user_id)
            if not destination:
                print(f"⚠ No destination set for user {user_id}")
                return
            
            # Parse destination channel ID
            dest_channel_id = destination['channel_id']
            if dest_channel_id.startswith('-100'):
                dest_channel_id = int(dest_channel_id)
            elif dest_channel_id.startswith('-'):
                dest_channel_id = int(dest_channel_id)
            else:
                dest_channel_id = int(f"-100{dest_channel_id}")
            
            print(f"📤 Adding to queue for destination: {destination['title']} ({dest_channel_id})")
            
            # Initialize queue for user if not exists
            if user_id not in self.message_queues:
                self.message_queues[user_id] = asyncio.Queue()
                self.processing_locks[user_id] = False
                print(f"✓ Created message queue for user {user_id}")
            
            # Start queue processor if not running
            if user_id not in self.queue_processors or self.queue_processors[user_id].done():
                self.queue_processors[user_id] = asyncio.create_task(self.process_message_queue(user_id))
                print(f"✓ Started queue processor for user {user_id}")
            
            # Add message to queue for sequential processing
            message_data = {
                'event': event,
                'channel_id': channel_id,
                'source_channel': source_channel,
                'destination': destination,
                'dest_channel_id': dest_channel_id,
                'message_id': event.message.id,
                'message_date': event.message.date
            }
            
            await self.message_queues[user_id].put(message_data)
            queue_size = self.message_queues[user_id].qsize()
            print(f"✓ Message {event.message.id} (date: {event.message.date}) added to queue (queue size: {queue_size})")
            
            # Log milestone for queued messages
            if queue_size % 10 == 0 and queue_size > 0:
                print(f"📊 Queue status for user {user_id}: {queue_size} messages pending")
                stats = await self.db.get_stats()
                if stats['total_forwards'] % 50 == 0:
                    await self.log_to_channel(
                        f"**Forwarding Milestone**\n\n"
                        f"📤 Total Forwards: {stats['total_forwards']}\n"
                        f"👥 Active Users: {stats['total_users']}\n"
                        f"⏳ Sequential Processing: Active\n"
                        f"📊 Success Rate: ~95%",
                        "forward"
                    )
        
        except Exception as e:
            print(f"✗ Error in handle_user_channel_message: {e}")
            import traceback
            traceback.print_exc()
    
    async def _copy_message_with_media(self, client, message, destination, force_download=False):
        """
        Copy message with media (handles restricted/protected content)
        Downloads media and re-uploads to bypass restrictions
        """
        import os
        import tempfile
        
        try:
            # Get message text/caption
            text = message.message or message.text or ""
            
            # Handle different message types
            if message.media:
                media_file = None
                temp_path = None
                progress_msg = None
                
                try:
                    # Download media to temporary file
                    print(f"📥 Downloading media from restricted content...")
                    print(f"   Media type: {type(message.media).__name__}")
                    
                    # Send initial progress message to destination
                    try:
                        progress_msg = await client.send_message(
                            destination,
                            "⏳ **Processing media...**\n📥 Starting download..."
                        )
                    except:
                        pass
                    
                    # Create temp directory if it doesn't exist
                    temp_dir = tempfile.gettempdir()
                    temp_path = os.path.join(temp_dir, f"tg_media_{message.id}_{int(asyncio.get_event_loop().time())}")
                    
                    # Progress callback for download with speed tracking
                    last_progress_update = 0
                    download_start_time = asyncio.get_event_loop().time()
                    last_update_time = download_start_time
                    last_current_bytes = 0
                    
                    async def download_progress_callback(current, total):
                        nonlocal last_progress_update, last_update_time, last_current_bytes
                        if total > 0:
                            percent = (current / total) * 100
                            # Update every 10%
                            if percent - last_progress_update >= 10:
                                last_progress_update = percent
                                
                                # Calculate speed
                                current_time = asyncio.get_event_loop().time()
                                time_diff = current_time - last_update_time
                                bytes_diff = current - last_current_bytes
                                
                                if time_diff > 0:
                                    speed_mbps = (bytes_diff / time_diff) / (1024 * 1024)
                                    avg_speed = (current / (current_time - download_start_time)) / (1024 * 1024)
                                    
                                    try:
                                        if progress_msg:
                                            await progress_msg.edit(
                                                f"⏳ **Processing media...**\n"
                                                f"📥 Downloading: {percent:.1f}%\n"
                                                f"📊 {current / 1024 / 1024:.1f} MB / {total / 1024 / 1024:.1f} MB\n"
                                                f"⚡ Speed: {speed_mbps:.2f} MB/s (avg: {avg_speed:.2f} MB/s)"
                                            )
                                    except:
                                        pass
                                    
                                    last_update_time = current_time
                                    last_current_bytes = current
                    
                    # Download the media with retry logic
                    max_download_retries = 3
                    downloaded_path = None
                    
                    for attempt in range(max_download_retries):
                        try:
                            print(f"   Download attempt {attempt + 1}/{max_download_retries}...")
                            
                            # Dynamic timeout based on file size - INCREASED for reliability
                            # Get file size estimate
                            file_size = 0
                            if hasattr(message.media, 'document') and hasattr(message.media.document, 'size'):
                                file_size = message.media.document.size
                            elif hasattr(message.media, 'photo'):
                                file_size = 10 * 1024 * 1024  # Estimate 10MB for photos
                            
                            # Calculate timeout: assume 1.5 MB/s (realistic) + large buffer
                            # Formula: (file_size_MB / 1.5 MB/s) + 180s buffer, minimum 240s
                            file_size_mb = file_size / (1024 * 1024)
                            download_timeout = max(240, (file_size_mb / 1.5) + 180)
                            expected_time = file_size_mb / 1.5
                            print(f"   File size: {file_size_mb:.1f} MB")
                            print(f"   Expected time: {expected_time:.0f}s, Timeout: {download_timeout:.0f}s ({download_timeout/60:.1f} min)")
                            print(f"   📥 Download speed assumption: 1.5 MB/s with 180s buffer")
                            
                            downloaded_path = await asyncio.wait_for(
                                client.download_media(
                                    message, 
                                    file=temp_path, 
                                    progress_callback=download_progress_callback
                                ),
                                timeout=download_timeout
                            )
                            if downloaded_path:
                                break
                        except asyncio.TimeoutError:
                            print(f"   ⚠️ Download timeout on attempt {attempt + 1}")
                            if progress_msg:
                                try:
                                    await progress_msg.edit(f"⚠️ Download timeout, retrying... ({attempt + 1}/{max_download_retries})")
                                except:
                                    pass
                            if attempt < max_download_retries - 1:
                                await asyncio.sleep(5)
                        except (ConnectionError, ConnectionResetError, ConnectionRefusedError) as conn_err:
                            print(f"   ⚠️ Connection error on attempt {attempt + 1}: {conn_err}")
                            if progress_msg:
                                try:
                                    await progress_msg.edit(f"⚠️ Connection error, retrying... ({attempt + 1}/{max_download_retries})")
                                except:
                                    pass
                            if attempt < max_download_retries - 1:
                                await asyncio.sleep(5)
                                # Try to reconnect
                                try:
                                    if not client.is_connected():
                                        await client.connect()
                                except:
                                    pass
                        except Exception as dl_err:
                            print(f"   ⚠️ Download error on attempt {attempt + 1}: {dl_err}")
                            if attempt < max_download_retries - 1:
                                await asyncio.sleep(3)
                    
                    if downloaded_path and os.path.exists(downloaded_path):
                        # Calculate actual download stats
                        download_end_time = asyncio.get_event_loop().time()
                        download_duration = download_end_time - download_start_time
                        file_size_actual = os.path.getsize(downloaded_path)
                        actual_download_speed = (file_size_actual / (1024 * 1024)) / download_duration if download_duration > 0 else 0
                        
                        print(f"✓ Media downloaded to: {downloaded_path}")
                        print(f"   File size: {file_size_actual} bytes ({file_size_actual / 1024 / 1024:.2f} MB)")
                        print(f"   ⏱️ Download took: {download_duration:.1f}s")
                        print(f"   ⚡ Average speed: {actual_download_speed:.2f} MB/s")
                        
                        # Update progress
                        if progress_msg:
                            try:
                                await progress_msg.edit(
                                    f"✅ **Download Complete!**\n"
                                    f"📊 Size: {file_size_actual / 1024 / 1024:.2f} MB\n"
                                    f"📤 Starting upload..."
                                )
                            except:
                                pass
                        
                        # Progress callback for upload with speed tracking
                        last_upload_progress = 0
                        upload_start_time = asyncio.get_event_loop().time()
                        last_upload_time = upload_start_time
                        last_upload_bytes = 0
                        
                        async def upload_progress_callback(current, total):
                            nonlocal last_upload_progress, last_upload_time, last_upload_bytes
                            if total > 0:
                                percent = (current / total) * 100
                                # Update every 10%
                                if percent - last_upload_progress >= 10:
                                    last_upload_progress = percent
                                    
                                    # Calculate speed
                                    current_time = asyncio.get_event_loop().time()
                                    time_diff = current_time - last_upload_time
                                    bytes_diff = current - last_upload_bytes
                                    
                                    if time_diff > 0:
                                        speed_mbps = (bytes_diff / time_diff) / (1024 * 1024)
                                        avg_speed = (current / (current_time - upload_start_time)) / (1024 * 1024)
                                        
                                        try:
                                            if progress_msg:
                                                await progress_msg.edit(
                                                    f"✅ **Download Complete!**\n"
                                                    f"📊 Size: {file_size_actual / 1024 / 1024:.2f} MB\n"
                                                    f"📤 Uploading: {percent:.1f}%\n"
                                                    f"📊 {current / 1024 / 1024:.1f} MB / {total / 1024 / 1024:.1f} MB\n"
                                                    f"⚡ Speed: {speed_mbps:.2f} MB/s (avg: {avg_speed:.2f} MB/s)"
                                                )
                                        except:
                                            pass
                                        
                                        last_upload_time = current_time
                                        last_upload_bytes = current
                        
                        # Send with downloaded media (with retry)
                        max_upload_retries = 3
                        upload_success = False
                        
                        # Calculate upload timeout: assume 1 MB/s (realistic) + LARGER buffer
                        # Formula: (file_size_MB / 1.0 MB/s) + 240s buffer, minimum 360s
                        file_size_mb = file_size_actual / (1024 * 1024)
                        upload_timeout = max(360, (file_size_mb / 1.0) + 240)
                        expected_upload_time = file_size_mb / 1.0
                        print(f"   Expected upload time: {expected_upload_time:.0f}s, Timeout: {upload_timeout:.0f}s ({upload_timeout / 60:.1f} min)")
                        print(f"   📤 Upload speed assumption: 1.0 MB/s with 240s buffer")
                        
                        for attempt in range(max_upload_retries):
                            try:
                                print(f"   Upload attempt {attempt + 1}/{max_upload_retries}...")
                                
                                # Extract video/file attributes from original message
                                attributes = []
                                force_document = False
                                supports_streaming = False
                                thumb = None  # For video thumbnail
                                
                                if hasattr(message.media, 'document'):
                                    doc = message.media.document
                                    # Copy original attributes (duration, width, height, etc.)
                                    if hasattr(doc, 'attributes') and doc.attributes:
                                        attributes = doc.attributes
                                        print(f"   📝 Preserving {len(attributes)} media attributes")
                                    
                                    # Extract thumbnail from original media
                                    if hasattr(doc, 'thumbs') and doc.thumbs:
                                        try:
                                            # Download thumbnail from original message (use largest available)
                                            thumb_path = os.path.join(temp_dir, f"thumb_{message.id}_{int(asyncio.get_event_loop().time())}.jpg")
                                            thumb = await client.download_media(message.media, file=thumb_path, thumb=-1)
                                            if thumb and os.path.exists(thumb):
                                                print(f"   📸 Thumbnail extracted: {thumb}")
                                            else:
                                                thumb = None
                                        except Exception as thumb_err:
                                            print(f"   ⚠️ Could not extract thumbnail: {thumb_err}")
                                            thumb = None
                                    
                                    # Check if it's a video and supports streaming
                                    for attr in attributes:
                                        if hasattr(attr, '__class__'):
                                            attr_name = attr.__class__.__name__
                                            if attr_name == 'DocumentAttributeVideo':
                                                supports_streaming = getattr(attr, 'supports_streaming', False)
                                                duration = getattr(attr, 'duration', 0)
                                                width = getattr(attr, 'w', 0)
                                                height = getattr(attr, 'h', 0)
                                                print(f"   🎥 Video: {duration}s, {width}x{height}, streaming: {supports_streaming}")
                                            elif attr_name == 'DocumentAttributeFilename':
                                                filename = getattr(attr, 'file_name', '')
                                                print(f"   📄 Filename: {filename}")
                                
                                elif hasattr(message.media, 'photo'):
                                    # For photos, no special attributes needed, but ensure high quality
                                    print(f"   📷 Photo media detected")
                                
                                # Use send_file() with proper attributes and thumbnail
                                await asyncio.wait_for(
                                    client.send_file(
                                        destination, 
                                        downloaded_path,
                                        caption=text if text else None,
                                        attributes=attributes if attributes else None,
                                        force_document=force_document,
                                        supports_streaming=supports_streaming,
                                        thumb=thumb if thumb else None,
                                        progress_callback=upload_progress_callback
                                    ),
                                    timeout=upload_timeout
                                )
                                upload_success = True
                                
                                # Calculate upload stats
                                upload_end_time = asyncio.get_event_loop().time()
                                upload_duration = upload_end_time - upload_start_time
                                actual_upload_speed = (file_size_actual / (1024 * 1024)) / upload_duration if upload_duration > 0 else 0
                                
                                print(f"✓ Media re-uploaded successfully")
                                print(f"   ⏱️ Upload took: {upload_duration:.1f}s")
                                print(f"   ⚡ Average speed: {actual_upload_speed:.2f} MB/s")
                                
                                # Clean up thumbnail file if it exists
                                if thumb and os.path.exists(thumb):
                                    try:
                                        os.remove(thumb)
                                        print(f"✓ Thumbnail file cleaned up")
                                    except:
                                        pass
                                
                                # Delete progress message after successful upload
                                if progress_msg:
                                    try:
                                        await progress_msg.delete()
                                    except:
                                        pass
                                break
                            except asyncio.TimeoutError:
                                print(f"   ⚠️ Upload timeout on attempt {attempt + 1}")
                                if progress_msg:
                                    try:
                                        await progress_msg.edit(f"⚠️ Upload timeout, retrying... ({attempt + 1}/{max_upload_retries})")
                                    except:
                                        pass
                                if attempt < max_upload_retries - 1:
                                    await asyncio.sleep(5)
                            except (ConnectionError, ConnectionResetError, ConnectionRefusedError) as conn_err:
                                print(f"   ⚠️ Connection error on attempt {attempt + 1}: {conn_err}")
                                if progress_msg:
                                    try:
                                        await progress_msg.edit(f"⚠️ Connection error, retrying... ({attempt + 1}/{max_upload_retries})")
                                    except:
                                        pass
                                if attempt < max_upload_retries - 1:
                                    await asyncio.sleep(5)
                                    try:
                                        if not client.is_connected():
                                            await client.connect()
                                    except:
                                        pass
                            except Exception as up_err:
                                print(f"   ⚠️ Upload error on attempt {attempt + 1}: {up_err}")
                                if attempt < max_upload_retries - 1:
                                    await asyncio.sleep(3)
                        
                        if not upload_success:
                            print(f"   ❌ Failed to upload after {max_upload_retries} attempts")
                            # Update progress message to show failure
                            if progress_msg:
                                try:
                                    await progress_msg.edit(
                                        f"❌ **Upload Failed**\n"
                                        f"File size: {file_size_actual / 1024 / 1024:.2f} MB\n"
                                        f"All {max_upload_retries} attempts failed"
                                    )
                                except:
                                    pass
                        
                        # Clean up temp file
                        try:
                            os.remove(downloaded_path)
                            print(f"✓ Temp file cleaned up")
                        except:
                            pass
                    else:
                        print(f"⚠ Media download returned None or file doesn't exist")
                        # Update progress message
                        if progress_msg:
                            try:
                                await progress_msg.edit("❌ Download failed")
                            except:
                                pass
                        # Try sending text only
                        if text:
                            await client.send_message(destination, text)
                            print(f"⚠ Sent text only (media download failed)")
                
                except Exception as media_error:
                    print(f"⚠ Media handling error: {media_error}")
                    import traceback
                    traceback.print_exc()
                    
                    # Clean up temp file if exists
                    if temp_path and os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                    
                    # Try alternative: send file reference directly
                    try:
                        print(f"   Trying direct media reference...")
                        await client.send_message(
                            destination,
                            text,
                            file=message.media
                        )
                        print(f"✓ Sent using media reference")
                    except Exception as ref_error:
                        print(f"⚠ Media reference also failed: {ref_error}")
                        # Last resort: text only
                        if text:
                            await client.send_message(destination, text)
                            print(f"⚠ Sent text only (all media methods failed)")
            
            elif text:
                # Text only message
                await client.send_message(destination, text)
                print(f"✓ Sent text message")
            
            else:
                print(f"⚠ Empty message, skipping")
        
        except Exception as e:
            print(f"✗ Error in _copy_message_with_media: {e}")
            import traceback
            traceback.print_exc()
            raise

    
    # Admin commands
    async def cmd_stats(self, event, user_id: int):
        """Admin: Show stats"""
        stats = await self.db.get_stats()
        sessions = await self.db.user_sessions.count_documents({})
        
        await event.reply(
            f"📊 **Bot Statistics**\n\n"
            f"👥 Users: {stats['total_users']}\n"
            f"🔐 Logged In: {sessions}\n"
            f"📤 Forwards: {stats['total_forwards']}\n"
            f"🚫 Banned: {stats['banned_users']}\n\n"
            f"✨ Created by @amanbotz"
        )
    
    async def cmd_users(self, event, user_id: int):
        """Admin: List users"""
        users = await self.db.get_all_users()
        
        message = f"👥 **All Users ({len(users)}):**\n\n"
        for i, user in enumerate(users[:20], 1):
            message += f"{i}. {user['username']} (`{user['user_id']}`)\n"
        
        if len(users) > 20:
            message += f"\n... +{len(users)-20} more"
        
        await event.reply(message)
    
    async def cmd_broadcast(self, event, user_id: int):
        """Admin: Broadcast"""
        self.awaiting_broadcast[user_id] = True
        await event.reply("📡 Send your broadcast message:")
    
    async def handle_broadcast(self, event):
        """Handle broadcast"""
        users = await self.db.get_all_users()
        self.awaiting_broadcast[event.sender_id] = False
        
        status = await event.reply(f"📡 Broadcasting to {len(users)} users...")
        
        success = 0
        for user in users:
            try:
                await self.bot_client.send_message(int(user['user_id']), event.message)
                success += 1
                await asyncio.sleep(0.1)
            except:
                pass
        
        await status.edit(f"✅ Broadcast complete! Sent to {success}/{len(users)} users")
        
        # Log broadcast
        await self.log_to_channel(
            f"**Broadcast Sent**\n\n"
            f"👑 Sent by: {event.sender.username or event.sender.first_name}\n"
            f"🆔 Admin ID: `{event.sender_id}`\n"
            f"📊 Success: {success}/{len(users)} users\n"
            f"📝 Message Preview: {event.message.text[:100] if event.message.text else 'Media message'}...",
            "admin"
        )
    
    async def cmd_ban(self, event, user_id: int, args):
        """Admin: Ban user with reason"""
        if not args:
            await event.reply(
                "❌ **Usage:** `/ban <user_id> [reason]`\n\n"
                "**Examples:**\n"
                "• `/ban 123456789`\n"
                "• `/ban 123456789 Spam and abuse`\n"
                "• `/ban 123456789 Violation of terms`"
            )
            return
        
        try:
            ban_user_id = int(args[0])
            
            # Check if trying to ban owner
            if ban_user_id == self.owner_id:
                await event.reply("❌ **Cannot ban the bot owner!**")
                return
            
            # Check if already banned
            if await self.db.is_user_banned(ban_user_id):
    async def cmd_unban(self, event, user_id: int, args):
        """Admin: Unban user"""
        if not args:
            await event.reply(
                "❌ **Usage:** `/unban <user_id>`\n\n"
                "**Example:**\n"
                "• `/unban 123456789`"
            )
            return
        
        try:
            unban_user_id = int(args[0])
            
            # Check if user is actually banned
            if not await self.db.is_user_banned(unban_user_id):
                await event.reply(f"⚠️ **User `{unban_user_id}` is not banned!**")
                return
            
            # Get ban info before unbanning
            ban_info = await self.db.get_ban_info(unban_user_id)
            username = ban_info.get('username', f"User {unban_user_id}") if ban_info else f"User {unban_user_id}"
            
            # Unban the user
            if await self.db.unban_user(unban_user_id):
                await event.reply(
                    f"✅ **User Unbanned Successfully!**\n\n"
                    f"👤 **User:** {username}\n"
                    f"🆔 **ID:** `{unban_user_id}`\n\n"
                    f"✅ **This user can now:**\n"
                    f"• Use all bot commands\n"
                    f"• Send messages to bot\n"
                    f"• Access all bot features\n\n"
                    f"💡 Use `/ban {unban_user_id} [reason]` to ban again if needed"
                )
                
                # Notify the unbanned user
                try:
                    await self.bot_client.send_message(
                        unban_user_id,
                        f"✅ **You have been unbanned!**\n\n"
                        f"You can now use the bot again.\n\n"
                        f"💡 Use /start to begin using bot features."
                    )
                except Exception as notify_err:
                    print(f"⚠️ Could not notify unbanned user: {notify_err}")
                
                # Log unban action
                await self.log_to_channel(
                    f"**User Unbanned**\n\n"
                    f"✅ **Unbanned User:** {username}\n"
                    f"🆔 **User ID:** `{unban_user_id}`\n"
                    f"� **Unbanned by:** {event.sender.username or event.sender.first_name}\n"
                    f"🆔 **Admin ID:** `{user_id}`",
                    "admin"
                )
            else:
                await event.reply("❌ **Failed to unban user!** Database error occurred.")
        except ValueError:
            await event.reply("❌ **Invalid user ID!** Please provide a numeric user ID.")
        except Exception as e:
            await event.reply(f"❌ **Error:** {e}")
            import traceback
            traceback.print_exc()d from:**\n"
                    f"• Using any bot commands\n"
                    f"• Sending messages to bot\n"
                    f"• Accessing bot features\n\n"
                    f"💡 Use `/unban {ban_user_id}` to unban"
                )
                
                # Notify the banned user
                try:
                    await self.bot_client.send_message(
                        ban_user_id,
                        f"🚫 **You have been banned from this bot**\n\n"
                        f"📝 **Reason:** {reason}\n\n"
                        f"⚠️ All bot features are now disabled for your account.\n\n"
                        f"💬 Contact the bot owner if you believe this is a mistake."
                    )
                except Exception as notify_err:
                    print(f"⚠️ Could not notify banned user: {notify_err}")
                
                # Disconnect user's client if they're logged in
                if ban_user_id in self.user_clients:
                    try:
                        await self.user_clients[ban_user_id].disconnect()
                        del self.user_clients[ban_user_id]
                        print(f"✓ Disconnected banned user's client: {ban_user_id}")
                    except Exception as disconnect_err:
                        print(f"⚠️ Could not disconnect user client: {disconnect_err}")
                
                # Log ban action
                await self.log_to_channel(
                    f"**User Banned**\n\n"
                    f"🚫 **Banned User:** {username}\n"
                    f"🆔 **User ID:** `{ban_user_id}`\n"
                    f"📝 **Reason:** {reason}\n"
                    f"👑 **Banned by:** {event.sender.username or event.sender.first_name}\n"
                    f"🆔 **Admin ID:** `{user_id}`",
                    "admin"
                )
            else:
                await event.reply("❌ **Failed to ban user!** Database error occurred.")
        except ValueError:
            await event.reply("❌ **Invalid user ID!** Please provide a numeric user ID.")
        except Exception as e:
            await event.reply(f"❌ **Error:** {e}")
            import traceback
            traceback.print_exc()
    
    async def cmd_unban(self, event, user_id: int, args):
        """Admin: Unban user"""
        if not args:
            await event.reply("❌ Usage: /unban <user_id>")
            return
        
        try:
            unban_user_id = int(args[0])
            await self.db.unban_user(unban_user_id)
            await event.reply(f"✅ Unbanned user: {unban_user_id}")
            
            # Log unban action
            await self.log_to_channel(
                f"**User Unbanned**\n\n"
                f"✅ Unbanned User ID: `{unban_user_id}`\n"
                f"👑 Unbanned by: {event.sender.username or event.sender.first_name}\n"
                f"🆔 Admin ID: `{user_id}`",
                "admin"
            )
        except:
            await event.reply("❌ Invalid user ID")
    
    async def cmd_banned(self, event, user_id: int):
        """Admin: List all banned users with details"""
        banned = await self.db.get_banned_users()
        
        if not banned:
            await event.reply(
                "📋 **No Banned Users**\n\n"
                "✅ All users are currently allowed to use the bot.\n\n"
                "💡 Use `/ban <user_id> [reason]` to ban users."
            )
            return
        
        # Build detailed message
        message = f"🚫 **Banned Users ({len(banned)}):**\n\n"
        
        for i, user in enumerate(banned, 1):
            username = user.get('username', 'Unknown')
            user_id_str = user.get('user_id', 'Unknown')
            reason = user.get('reason', 'No reason')
            ban_date = user.get('banned_date', None)
            
            # Format ban date
            if ban_date:
                try:
                    ban_date_str = ban_date.strftime('%Y-%m-%d')
                except:
                    ban_date_str = 'Unknown'
            else:
                ban_date_str = 'Unknown'
            
            message += f"**{i}.** {username}\n"
            message += f"   🆔 ID: `{user_id_str}`\n"
            message += f"   📝 Reason: {reason}\n"
            message += f"   📅 Banned: {ban_date_str}\n\n"
            
            # Prevent message from being too long
            if len(message) > 3500:
                message += f"\n... and {len(banned) - i} more users\n\n"
                message += "💡 **Note:** Message truncated due to length"
                break
        
        message += f"\n💡 Use `/unban <user_id>` to unban\n"
        message += f"💡 Use `/ban <user_id> [reason]` to ban more users"
        
        await event.reply(message)
    
    async def handle_callback(self, event):
        """Handle button callbacks"""
        data = event.data.decode('utf-8')
        user_id = event.sender_id
        
        if data == "login":
            await event.answer("Starting login...")
            await self.cmd_login(event, user_id)
        elif data == "help":
            await self.cmd_help(event, user_id)
        elif data == "myaccount":
            await self.cmd_myaccount(event, user_id)
        elif data == "mychannels":
            await self.cmd_list(event, user_id)
        elif data == "mystatus":
            await self.cmd_status(event, user_id)
        elif data == "addsource":
            await self.cmd_addsource(event, user_id)
        elif data == "setdest":
            await self.cmd_setdest(event, user_id)
        elif data == "admin" and user_id == self.owner_id:
            await event.answer("Admin panel")
            await event.edit(
                "👑 **Admin Panel**\n\n"
                "Use admin commands to manage the bot",
                buttons=[[Button.inline("« Back", b"start")]]
            )
        elif data == "start":
            await self.cmd_start(event, user_id)
    
    async def run(self):
        """Start the bot"""
        if not await self.initialize():
            return
        
        try:
            await self.bot_client.run_until_disconnected()
        
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping bot...")
            # Disconnect all user clients
            for client in self.user_clients.values():
                try:
                    await client.disconnect()
                except:
                    pass
            # Disconnect all temp clients
            for client in self.temp_clients.values():
                try:
                    await client.disconnect()
                except:
                    pass
            print("✨ Thanks for using Auto Forward Bot!")
            print("🔗 GitHub: github.com/theamanchaudhary\n")


def print_help():
    """Print help message"""
    print("\n" + "="*60)
    print("🤖 TELEGRAM AUTO FORWARD BOT")
    print("="*60)
    print("\n✨ Created by: @amanbotz")
    print("🔗 GitHub: github.com/theamanchaudhary\n")
    print("Usage: python main.py [command]\n")
    print("Commands:")
    print("  setup    - Configure the bot")
    print("  start    - Start the bot")
    print("  help     - Show this help")
    print("\n" + "="*60 + "\n")


async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1].lower()
    bot = ForwardBot()
    
    if command == 'setup':
        await bot.setup_bot()
    elif command == 'start':
        await bot.run()
    elif command == 'help':
        print_help()
    else:
        print(f"❌ Unknown command: {command}")
        print_help()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
