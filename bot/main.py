import logging
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import Config
from handlers import (
    start, help_command, analyze_command, synthesize_command,
    adme_command, toxicity_command, history_command, formula_command,
    research_command, status_command, handle_message
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def create_app():
    Config.validate()
    
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("synthesize", synthesize_command))
    application.add_handler(CommandHandler("adme", adme_command))
    application.add_handler(CommandHandler("toxicity", toxicity_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("formula", formula_command))
    application.add_handler(CommandHandler("research", research_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # Message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    return application

async def error_handler(update, context):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An error occurred. Please try again or use `/help` for assistance."
        )

def main():
    app = create_app()
    logger.info("⚗️ Denia Pharmacist is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
