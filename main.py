import os
import requests
import base64
from flask import Flask, request, jsonify
from telegram import Bot, Update
from telegram.ext import Dispatcher, MessageHandler, Filters, CommandHandler
import google.generativeai as genai
from io import BytesIO
from PIL import Image
import logging

# Initialize Flask app
app = Flask(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Initialize clients
bot = Bot(token=TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook handler for Telegram"""
    if request.method == 'POST':
        update = Update.de_json(request.get_json(), bot)
        
        if update.message:
            handle_message(update.message)
        elif update.callback_query:
            handle_callback(update.callback_query)
            
    return jsonify({'status': 'ok'})

def handle_message(message):
    """Handle incoming messages"""
    chat_id = message.chat.id
    
    try:
        if message.photo:
            handle_plant_analysis(message)
        elif message.text:
            handle_text_message(message)
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        bot.send_message(chat_id, "❌ Sorry, I encountered an error. Please try again.")

def handle_text_message(message):
    """Handle text messages"""
    chat_id = message.chat.id
    text = message.text.strip()
    
    if text.startswith('/'):
        handle_commands(message)
    else:
        welcome_text = "🌿 Plant Doctor Bot - Send me a plant photo for analysis!"
        bot.send_message(chat_id, welcome_text, parse_mode='Markdown')

def handle_commands(message):
    """Handle bot commands"""
    chat_id = message.chat.id
    text = message.text.strip().lower()
    
    if text == '/start' or text == '/help':
        welcome_text = """
🌱 *Plant Doctor Bot*

Send me a photo of your plant for AI analysis!

Commands:
/start - Show this message
/analyze - Analyze a plant photo
"""
        bot.send_message(chat_id, welcome_text, parse_mode='Markdown')
    
    elif text == '/analyze':
        bot.send_message(chat_id, "📸 Please send me a photo of your plant for analysis.")

def handle_plant_analysis(message):
    """Analyze plant photo using Google Gemini"""
    chat_id = message.chat.id
    
    try:
        processing_msg = bot.send_message(chat_id, "🔍 Analyzing your plant photo...")
        
        # Get the highest quality photo
        photo_file = message.photo[-1].get_file()
        
        # Download photo
        photo_bytes = BytesIO()
        photo_file.download(out=photo_bytes)
        photo_bytes.seek(0)
        
        # Open as PIL Image
        img = Image.open(photo_bytes)
        
        # Analyze with Gemini
        analysis = analyze_plant_with_gemini(img)
        
        # Delete processing message
        bot.delete_message(chat_id, processing_msg.message_id)
        
        # Send results
        send_analysis_results(chat_id, analysis)
        
    except Exception as e:
        logger.error(f"Error analyzing plant: {e}")
        bot.send_message(chat_id, f"❌ Sorry, I couldn't analyze the image. Error: {str(e)}")

def analyze_plant_with_gemini(image):
    """Use Google Gemini to analyze plant issues"""
    
    prompt = """
Analyze this plant photo and provide a comprehensive diagnosis:

Please provide:
1. **Likely Issue**: What problem the plant might have
2. **Symptoms**: Visible signs in the photo
3. **Causes**: Possible reasons for the issue
4. **Treatment**: Step-by-step solutions
5. **Prevention**: How to avoid recurrence

Be specific and practical in your advice.
"""
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([prompt, image])
        
        return response.text
        
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise Exception(f"Gemini API error: {str(e)}")

def send_analysis_results(chat_id, analysis):
    """Send formatted analysis results to user"""
    
    formatted_response = f"""
🌿 *Plant Analysis Results*

{analysis}

💡 *Remember*: This is an AI analysis. For serious plant issues, consult a local expert.
"""
    
    # Escape markdown special characters in analysis
    analysis_escaped = analysis.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]')
    formatted_response = f"""
🌿 *Plant Analysis Results*

{analysis_escaped}

💡 *Remember*: This is an AI analysis. For serious plant issues, consult a local expert.
"""
    
    if len(formatted_response) > 4000:
        chunks = [formatted_response[i:i+4000] for i in range(0, len(formatted_response), 4000)]
        for chunk in chunks:
            try:
                bot.send_message(chat_id, chunk, parse_mode='Markdown')
            except:
                bot.send_message(chat_id, chunk)  # Send without markdown if it fails
    else:
        try:
            bot.send_message(chat_id, formatted_response, parse_mode='Markdown')
        except:
            bot.send_message(chat_id, formatted_response)  # Send without markdown if it fails

def handle_callback(callback_query):
    """Handle callback queries"""
    chat_id = callback_query.message.chat.id
    bot.answer_callback_query(callback_query.id)
    bot.send_message(chat_id, "Feature coming soon!")

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Set webhook URL for Telegram"""
    webhook_url = os.getenv('WEBHOOK_URL')
    if not webhook_url:
        return "WEBHOOK_URL environment variable not set", 400
    
    result = bot.set_webhook(webhook_url)
    if result:
        return f"Webhook set successfully: {webhook_url}"
    else:
        return "Failed to set webhook", 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

@app.route('/')
def home():
    return "🌿 Plant Doctor Bot is running!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)