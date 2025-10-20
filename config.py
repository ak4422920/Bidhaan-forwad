# config.py
"""
Configuration Manager for Telegram Forward Bot
Created by: @amanbotz
GitHub: https://github.com/theamanchaudhary
"""

import json
import os
from dataclasses import dataclass, asdict

@dataclass
class BotConfig:
    """Bot configuration data class"""
    # Telegram API Credentials
    api_id: int = int(os.getenv('API_ID', '26385571'))
    api_hash: str = os.getenv('API_HASH', 'aac7a3c3c2f36e72201a6a5a21eb802a')
    bot_token: str = os.getenv('BOT_TOKEN', '8495685889:AAGM2RGzSioKB_MBDy2AyYy77DQx_IGjCHE')
    
    # MongoDB Configuration
    mongo_uri: str = os.getenv('MONGO_URI', 'mongodb+srv://BIGFIISH:iFyAm2DZqEzo76VW@cluster0.z6bhz.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
    mongo_db_name: str = os.getenv('MONGO_DB_NAME', 'forward_bot')
    
    # Bot Settings
    owner_id: int = int(os.getenv('OWNER_ID', '6169808990'))
    log_channel: int = int(os.getenv('LOG_CHANNEL', '-1003151867792'))

class ConfigManager:
    """Manages bot configuration"""
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = BotConfig()
    
    def load_config(self) -> BotConfig:
        """Load configuration from file or environment variables"""
        # First try to load from environment variables (for Heroku/Docker)
        if os.getenv('BOT_TOKEN'):
            print(f"✓ Configuration loaded from environment variables")
            self.config = BotConfig()
            return self.config
        
        # Otherwise load from config file
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    # Override with environment variables if they exist
                    if os.getenv('API_ID'):
                        data['api_id'] = int(os.getenv('API_ID'))
                    if os.getenv('API_HASH'):
                        data['api_hash'] = os.getenv('API_HASH')
                    if os.getenv('BOT_TOKEN'):
                        data['bot_token'] = os.getenv('BOT_TOKEN')
                    if os.getenv('MONGO_URI'):
                        data['mongo_uri'] = os.getenv('MONGO_URI')
                    if os.getenv('MONGO_DB_NAME'):
                        data['mongo_db_name'] = os.getenv('MONGO_DB_NAME')
                    if os.getenv('OWNER_ID'):
                        data['owner_id'] = int(os.getenv('OWNER_ID'))
                    if os.getenv('LOG_CHANNEL'):
                        data['log_channel'] = int(os.getenv('LOG_CHANNEL'))
                    
                    self.config = BotConfig(**data)
                    print(f"✓ Configuration loaded from file")
            except Exception as e:
                print(f"⚠ Error loading config: {e}")
                self.config = BotConfig()
        else:
            self.config = BotConfig()
        
        return self.config
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(asdict(self.config), f, indent=4)
            print(f"✓ Configuration saved")
        except Exception as e:
            print(f"✗ Error saving config: {e}")
