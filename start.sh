#!/bin/bash
# Heroku startup script

echo "🚀 Starting Telegram Auto Forward Bot on Heroku..."
echo "✨ Created by: @NullZoro"
echo "🔗 "

# Check if all required environment variables are set
if [ -z "$API_ID" ] || [ -z "$API_HASH" ] || [ -z "$BOT_TOKEN" ] || [ -z "$MONGO_URI" ] || [ -z "$OWNER_ID" ]; then
    echo "❌ Error: Missing required environment variables"
    echo "Required: API_ID, API_HASH, BOT_TOKEN, MONGO_URI, OWNER_ID"
    exit 1
fi

echo "✅ Environment variables loaded"
echo "📊 Configuration:"
echo "   • API_ID: Set"
echo "   • API_HASH: Set"
echo "   • BOT_TOKEN: Set"
echo "   • MONGO_URI: Set"
echo "   • MONGO_DB_NAME: ${MONGO_DB_NAME:-forward_bot}"
echo "   • OWNER_ID: $OWNER_ID"
echo "   • LOG_CHANNEL: ${LOG_CHANNEL:-Not Set}"

# Start the bot
exec python main.py start
