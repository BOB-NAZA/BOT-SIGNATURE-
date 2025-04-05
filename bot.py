import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import pickle
import os
from flask import Flask
from threading import Thread

# Configuration initiale
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration Flask pour keep-alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Telegram en fonctionnement"

def run_flask():
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5000))

# Fichier de stockage
STORAGE_FILE = "channels_data.pkl"

class ChannelStorage:
    def __init__(self):
        self.channels = {}
        self.load_data()
    
    def load_data(self):
        if os.path.exists(STORAGE_FILE):
            try:
                with open(STORAGE_FILE, 'rb') as f:
                    self.channels = pickle.load(f)
            except Exception as e:
                logger.error(f"Erreur chargement données: {e}")
                self.channels = {}
    
    def save_data(self):
        with open(STORAGE_FILE, 'wb') as f:
            pickle.dump(self.channels, f)
    
    def add_channel(self, channel_id, channel_name):
        self.channels[channel_id] = channel_name
        self.save_data()
    
    def remove_channel(self, channel_id):
        if channel_id in self.channels:
            del self.channels[channel_id]
            self.save_data()
            return True
        return False
    
    def get_channels(self):
        return self.channels

storage = ChannelStorage()

# Commandes du bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("➕ Ajouter une chaîne", callback_data='add_channel'),
            InlineKeyboardButton("🗑 Supprimer une chaîne", callback_data='remove_channel'),
        ],
        [
            InlineKeyboardButton("📋 Liste des chaînes", callback_data='list_channels'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Menu principal:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'add_channel':
        await query.edit_message_text(
            text="Envoyez le @nom ou l'ID numérique de la chaîne\n"
            "(Le bot doit être admin de la chaîne)"
        )
        context.user_data['awaiting_channel'] = True
    elif query.data == 'remove_channel':
        await show_channels_to_remove(query, context)
    elif query.data == 'list_channels':
        await show_channels_list(query, context)
    elif query.data.startswith('remove_'):
        channel_id = query.data[7:]
        if storage.remove_channel(channel_id):
            await query.edit_message_text(f"✅ Chaîne supprimée")
        else:
            await query.edit_message_text("❌ Chaîne introuvable")
    elif query.data == 'back_to_menu':
        await start_from_button(query, context)

async def start_from_button(query, context):
    keyboard = [
        [
            InlineKeyboardButton("➕ Ajouter une chaîne", callback_data='add_channel'),
            InlineKeyboardButton("🗑 Supprimer une chaîne", callback_data='remove_channel'),
        ],
        [
            InlineKeyboardButton("📋 Liste des chaînes", callback_data='list_channels'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('Menu principal:', reply_markup=reply_markup)

async def show_channels_to_remove(query, context):
    channels = storage.get_channels()
    if not channels:
        await query.edit_message_text("Aucune chaîne configurée")
        return
    
    keyboard = []
    for channel_id, channel_name in channels.items():
        keyboard.append([InlineKeyboardButton(
            f"🗑 {channel_name}",
            callback_data=f'remove_{channel_id}'
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data='back_to_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Sélectionnez une chaîne à supprimer:", reply_markup=reply_markup)

async def show_channels_list(query, context):
    channels = storage.get_channels()
    if not channels:
        await query.edit_message_text("Aucune chaîne configurée")
        return
    
    message = "📋 Chaînes configurées:\n\n"
    for channel_id, channel_name in channels.items():
        message += f"• {channel_name} (ID: {channel_id})\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Retour", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'awaiting_channel' in context.user_data:
        channel_input = update.message.text.strip()
        
        if channel_input.startswith('@'):
            channel_name = channel_input
            channel_id = channel_name[1:]
            storage.add_channel(channel_id, channel_name)
            await update.message.reply_text(f"✅ {channel_name} ajoutée!")
        elif channel_input.isdigit():
            channel_id = channel_input
            channel_name = f"Chaîne {channel_id}"
            storage.add_channel(channel_id, channel_name)
            await update.message.reply_text(f"✅ ID {channel_id} ajouté!")
        else:
            await update.message.reply_text("❌ Format invalide. Utilisez @nom ou ID numérique")
        
        del context.user_data['awaiting_channel']
    else:
        await update.message.reply_text("Utilisez /start pour le menu")

async def edit_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.channel_post:
        message = update.channel_post
        channel_id = str(message.chat.id)
        
        channels = storage.get_channels()
        if channel_id in channels:
            channel_name = channels[channel_id]
            signature = f"\n\n@{channel_name}"
            
            if message.text and not message.text.endswith(signature):
                try:
                    await message.edit_text(message.text + signature)
                except Exception as e:
                    logger.error(f"Erreur édition: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Erreur:", exc_info=context.error)

def main() -> None:
    """Lance le bot avec polling pour smartphone"""
     TOKEN = os.getenv('BOT-TO')
    
    # Crée l'application
    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POSTS, edit_messages))
    application.add_error_handler(error_handler)

    # Lance Flask dans un thread séparé
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Démarre le bot
    logger.info("Démarrage du bot en mode polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
