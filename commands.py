# commands.py
"""
Command Handler for Telegram Forward Bot
Created by: @amanbotz
GitHub: https://github.com/theamanchaudhary
"""

from telethon import TelegramClient, Button
from config import ConfigManager, BotConfig
from database import Database
from datetime import datetime
import sys

class BotCommands:
    """Handles bot commands"""
    
    def __init__(self, client: TelegramClient, config: BotConfig, config_manager: ConfigManager, db: Database, bot_instance):
        self.client = client
        self.config = config
        self.config_manager = config_manager
        self.db = db
        self.bot = bot_instance
    
    async def handle_command(self, command: str, args: list, event):
        """Route command to appropriate handler"""
        user_id = event.sender_id
        
        # Public commands (available to all users)
        public_commands = {
            'start': self.cmd_start,
            'help': self.cmd_help,
        }
        
        # Owner only commands
        owner_commands = {
            'status': self.cmd_status,
            'addsource': self.cmd_addsource,
            'setdest': self.cmd_setdest,
            'remove': self.cmd_remove,
            'list': self.cmd_list,
            'mode': self.cmd_mode,
            'broadcast': self.cmd_broadcast,
            'ban': self.cmd_ban,
            'unban': self.cmd_unban,
            'banned': self.cmd_banned,
            'stats': self.cmd_stats,
            'users': self.cmd_users,
            'stop': self.cmd_stop,
        }
        
        # Check if command exists
        if command in public_commands:
            await public_commands[command](args, event)
        elif command in owner_commands:
            if user_id == self.bot.owner_id:
                await owner_commands[command](args, event)
            else:
                await event.reply("❌ This command is only for bot owner!")
        else:
            await event.reply(f"❌ Unknown command: /{command}\n\nType /help for available commands")
    
    async def cmd_start(self, args, event):
        """Welcome message"""
        user_id = event.sender_id
        is_owner = user_id == self.bot.owner_id
        
        if is_owner:
            buttons = [
                [Button.inline("📊 Stats", b"stats"), Button.inline("📋 Channels", b"list")],
                [Button.inline("👥 Users", b"users"), Button.inline("🚫 Banned", b"banned")],
                [Button.inline("📡 Broadcast", b"broadcast"), Button.inline("❓ Help", b"help")]
            ]
        else:
            buttons = [
                [Button.inline("❓ Help", b"help"), Button.inline("📞 Support", b"support")]
            ]
        
        welcome_text = f"""
👋 **Welcome to Auto Forward Bot!**

{"🔐 **Owner Panel**" if is_owner else "ℹ️ **User Mode**"}

This bot automatically forwards messages from source channels to your destination channel.

{"✨ **Quick Actions:**\n• /addsource - Add source channel\n• /setdest - Set destination\n• /stats - View statistics\n• /broadcast - Send message to all users" if is_owner else "💡 For bot setup, contact the owner."}

{"" if is_owner else "🤖 **Bot Features:**\n• Auto forward messages\n• Copy or Forward mode\n• Multi-channel support"}

✨ **Created by:** @amanbotz
🔗 **GitHub:** github.com/theamanchaudhary
"""
        await event.reply(welcome_text, buttons=buttons)
    
    async def cmd_help(self, args, event):
        """Show help message"""
        user_id = event.sender_id
        is_owner = user_id == self.bot.owner_id
        
        if is_owner:
            help_text = """
🤖 **Bot Commands - Owner Panel**

📥 **Channel Management:**
/addsource - Add source channel (forward a message)
/setdest - Set destination (forward a message)
/list - Show all source channels
/remove <number> - Remove channel
/mode <number> <copy|forward> - Change mode

👥 **User Management:**
/users - Show all users
/ban <user_id> [reason] - Ban a user
/unban <user_id> - Unban a user
/banned - Show banned users

📊 **Statistics:**
/stats - Bot statistics
/status - Current bot status

📡 **Broadcasting:**
/broadcast - Send message to all users

⚙️ **Control:**
/stop - Stop the bot
/help - Show this message

📋 **Forward Modes:**
• **copy** - New message (no forward tag)
• **forward** - With attribution

✨ Created by @amanbotz
🔗 GitHub: github.com/theamanchaudhary
"""
        else:
            help_text = """
🤖 **Bot Information**

This is an auto-forward bot that helps channel owners automatically forward messages.

💡 **Features:**
• Multi-channel support
• Copy or Forward mode
• Real-time forwarding
• User management

📞 **Need Help?**
Contact the bot owner for setup and support.

✨ Created by @AkMovieVerse
🔗 GK: https://t.me/Akmovieshubx
"""
        
        await event.reply(help_text)
    
    async def cmd_status(self, args, event):
        """Show bot status"""
        channels = await self.db.get_all_channels()
        destination = await self.db.get_destination()
        
        copy_count = sum(1 for ch in channels if ch['forward_mode'] == 'copy')
        forward_count = len(channels) - copy_count
        
        status = f"""
🤖 **Bot Status**

📊 **Configuration:**
• Source Channels: {len(channels)}
• Destination: {'✅ Set' if destination else '❌ Not set'}

📋 **Forward Modes:**
• Copy Mode: {copy_count} channels
• Forward Mode: {forward_count} channels

👥 **Users:** {await self.db.get_user_count()}
🚫 **Banned:** {len(await self.db.get_banned_users())}

✨ Created by @amanbotz
🔗 GitHub: github.com/theamanchaudhary
"""
        await event.reply(status)
    
    async def cmd_addsource(self, args, event):
        """Prepare to add source channel"""
        self.bot.awaiting_source_forward[event.sender_id] = True
        self.bot.awaiting_destination_forward[event.sender_id] = False
        
        await event.reply(
            "📥 **Add Source Channel**\n\n"
            "Now forward ANY message from the channel you want to monitor.\n\n"
            "💡 **How to forward:**\n"
            "1. Go to the source channel\n"
            "2. Long press any message\n"
            "3. Tap 'Forward'\n"
            "4. Send it here\n\n"
            "The channel will be added automatically!"
        )
    
    async def cmd_setdest(self, args, event):
        """Prepare to set destination"""
        self.bot.awaiting_destination_forward[event.sender_id] = True
        self.bot.awaiting_source_forward[event.sender_id] = False
        
        await event.reply(
            "📤 **Set Destination Channel**\n\n"
            "Now forward ANY message from your destination channel.\n\n"
            "⚠️ **Important:**\n"
            "Make sure you are admin with post permissions!\n\n"
            "Forward any message from the destination channel now."
        )
    
    async def cmd_remove(self, args, event):
        """Remove a source channel"""
        if not args:
            await event.reply("❌ Usage: /remove <number>\n\nUse /list to see channels")
            return
        
        try:
            channels = await self.db.get_all_channels()
            index = int(args[0]) - 1
            
            if 0 <= index < len(channels):
                channel = channels[index]
                if await self.db.remove_source_channel(channel['channel_id']):
                    await event.reply(f"✅ Removed: **{channel['title']}**")
                else:
                    await event.reply("❌ Failed to remove channel")
            else:
                await event.reply("❌ Invalid number! Use /list")
        except ValueError:
            await event.reply("❌ Please provide a valid number")
    
    async def cmd_list(self, args, event):
        """List all source channels"""
        channels = await self.db.get_all_channels()
        
        if not channels:
            await event.reply("📋 **No source channels**\n\nUse /addsource to add")
            return
        
        message = "📋 **Source Channels:**\n\n"
        for i, ch in enumerate(channels, 1):
            mode_icon = "📋" if ch['forward_mode'] == 'copy' else "➡️"
            message += f"**{i}.** {mode_icon} {ch['title']}\n"
            message += f"   Mode: `{ch['forward_mode']}`\n"
            message += f"   ID: `{ch['channel_id']}`\n\n"
        
        message += "\n💡 /remove <number> - Remove channel\n"
        message += "💡 /mode <number> <mode> - Change mode"
        
        await event.reply(message)
    
    async def cmd_mode(self, args, event):
        """Change forward mode"""
        if len(args) < 2:
            await event.reply("❌ Usage: /mode <number> <copy|forward>")
            return
        
        try:
            channels = await self.db.get_all_channels()
            index = int(args[0]) - 1
            mode = args[1].lower()
            
            if mode not in ['copy', 'forward']:
                await event.reply("❌ Mode must be 'copy' or 'forward'")
                return
            
            if 0 <= index < len(channels):
                channel = channels[index]
                if await self.db.set_forward_mode(channel['channel_id'], mode):
                    await event.reply(
                        f"✅ **Mode changed!**\n\n"
                        f"📢 {channel['title']}\n"
                        f"🔄 New mode: {mode}"
                    )
                else:
                    await event.reply("❌ Failed to change mode")
            else:
                await event.reply("❌ Invalid number! Use /list")
        except ValueError:
            await event.reply("❌ Please provide valid number")
    
    async def cmd_broadcast(self, args, event):
        """Prepare for broadcast"""
        self.bot.awaiting_broadcast[event.sender_id] = True
        
        await event.reply(
            "📡 **Broadcast Mode**\n\n"
            "Send the message you want to broadcast to all users.\n\n"
            "💡 You can send:\n"
            "• Text messages\n"
            "• Photos with caption\n"
            "• Videos with caption\n"
            "• Documents\n\n"
            "⚠️ The message will be sent to all bot users!"
        )
    
    async def cmd_ban(self, args, event):
        """Ban a user"""
        if not args:
            await event.reply("❌ Usage: /ban <user_id> [reason]")
            return
        
        try:
            user_id = int(args[0])
            reason = " ".join(args[1:]) if len(args) > 1 else "No reason provided"
            
            if user_id == self.bot.owner_id:
                await event.reply("❌ Cannot ban the owner!")
                return
            
            # Get username
            try:
                user = await self.client.get_entity(user_id)
                username = user.username or user.first_name
            except:
                username = "Unknown"
            
            if await self.db.ban_user(user_id, username, reason):
                await event.reply(
                    f"✅ **User Banned**\n\n"
                    f"👤 User: {username}\n"
                    f"🆔 ID: `{user_id}`\n"
                    f"📝 Reason: {reason}"
                )
            else:
                await event.reply("❌ Failed to ban user")
        except ValueError:
            await event.reply("❌ Invalid user ID")
    
    async def cmd_unban(self, args, event):
        """Unban a user"""
        if not args:
            await event.reply("❌ Usage: /unban <user_id>")
            return
        
        try:
            user_id = int(args[0])
            
            if await self.db.unban_user(user_id):
                await event.reply(f"✅ User `{user_id}` has been unbanned")
            else:
                await event.reply("❌ User not found in ban list")
        except ValueError:
            await event.reply("❌ Invalid user ID")
    
    async def cmd_banned(self, args, event):
        """Show banned users"""
        banned = await self.db.get_banned_users()
        
        if not banned:
            await event.reply("📋 **No banned users**")
            return
        
        message = f"🚫 **Banned Users ({len(banned)}):**\n\n"
        for user in banned:
            message += f"👤 {user['username']}\n"
            message += f"🆔 `{user['user_id']}`\n"
            message += f"📝 {user['reason']}\n"
            message += f"📅 {user['banned_date'].strftime('%Y-%m-%d %H:%M')}\n\n"
        
        message += "\n💡 /unban <user_id> to unban"
        await event.reply(message)
    
    async def cmd_stats(self, args, event):
        """Show detailed statistics"""
        stats = await self.db.get_stats()
        
        days_active = (datetime.now() - stats['start_date']).days
        
        message = f"""
📊 **Bot Statistics**

👥 **Users:**
• Total Users: {stats['total_users']}
• Banned Users: {stats['banned_users']}
• Active Users: {stats['total_users'] - stats['banned_users']}

📢 **Channels:**
• Source Channels: {stats['total_channels']}
• Total Forwards: {stats['total_forwards']}

📅 **Activity:**
• Bot Started: {stats['start_date'].strftime('%Y-%m-%d')}
• Days Active: {days_active}
• Avg Forwards/Day: {stats['total_forwards'] // max(days_active, 1)}

✨ Created by @AkMovieVerse
🔗 GK: https://t.me/Akmovieshubx
"""
        await event.reply(message)
    
    async def cmd_users(self, args, event):
        """Show all users"""
        users = await self.db.get_all_users()
        
        if not users:
            await event.reply("📋 **No users yet**")
            return
        
        # Show first 20 users
        message = f"👥 **Bot Users ({len(users)}):**\n\n"
        for i, user in enumerate(users[:20], 1):
            message += f"{i}. {user['username']}\n"
            message += f"   ID: `{user['user_id']}`\n"
            message += f"   Joined: {user['joined_date'].strftime('%Y-%m-%d')}\n\n"
        
        if len(users) > 20:
            message += f"\n... and {len(users) - 20} more users"
        
        await event.reply(message)
    
    async def cmd_stop(self, args, event):
        """Stop the bot"""
        await event.reply(
            "🛑 **Stopping bot...**\n\n"
            "Bot will shutdown now.\n\n"
            "Run `python main.py start` to restart.\n\n"
            "✨ Created by @AkMovieVerse\n"
            "🔗 GitHub: github.com"
        )
        print("\n✓ Bot stopped by command")
        await self.client.disconnect()
        sys.exit(0)
    
    async def handle_callback(self, event):
        """Handle button callbacks"""
        data = event.data.decode('utf-8')
        user_id = event.sender_id
        
        if user_id != self.bot.owner_id:
            await event.answer("❌ Only owner can use this!", alert=True)
            return
        
        if data == "stats":
            await event.answer("Loading stats...")
            stats = await self.db.get_stats()
            await event.edit(
                f"📊 **Statistics**\n\n"
                f"👥 Users: {stats['total_users']}\n"
                f"📢 Channels: {stats['total_channels']}\n"
                f"📤 Forwards: {stats['total_forwards']}\n"
                f"🚫 Banned: {stats['banned_users']}",
                buttons=[[Button.inline("« Back", b"start")]]
            )
        
        elif data == "list":
            await event.answer("Loading channels...")
            channels = await self.db.get_all_channels()
            if channels:
                msg = "📋 **Channels:**\n\n"
                for i, ch in enumerate(channels[:10], 1):
                    mode = "📋" if ch['forward_mode'] == 'copy' else "➡️"
                    msg += f"{i}. {mode} {ch['title']}\n"
                if len(channels) > 10:
                    msg += f"\n... +{len(channels)-10} more"
            else:
                msg = "No channels configured"
            await event.edit(msg, buttons=[[Button.inline("« Back", b"start")]])
        
        elif data == "users":
            await event.answer("Loading users...")
            count = await self.db.get_user_count()
            await event.edit(
                f"👥 **Total Users:** {count}\n\nUse /users for full list",
                buttons=[[Button.inline("« Back", b"start")]]
            )
        
        elif data == "banned":
            await event.answer("Loading banned users...")
            banned = await self.db.get_banned_users()
            if banned:
                msg = f"🚫 **Banned ({len(banned)}):**\n\n"
                for user in banned[:5]:
                    msg += f"• {user['username']}\n"
                if len(banned) > 5:
                    msg += f"\n... +{len(banned)-5} more"
            else:
                msg = "No banned users"
            await event.edit(msg, buttons=[[Button.inline("« Back", b"start")]])
        
        elif data == "broadcast":
            await event.answer("Preparing broadcast...")
            self.bot.awaiting_broadcast[user_id] = True
            await event.edit(
                "📡 **Broadcast Mode**\n\nSend your message now",
                buttons=[[Button.inline("« Cancel", b"start")]]
            )
        
        elif data == "help":
            await self.cmd_help([], event)
        
        elif data == "support":
            await event.edit(
                "📞 **Support**\n\n"
                "Contact: @AkMovieVerse\n"
                "GK: https://t.me/Akmovieshubx",
                buttons=[[Button.inline("« Back", b"start")]]
            )
        
        elif data == "start":
            await self.cmd_start([], event)

