import os
import requests
import base64
from flask import Flask, request, jsonify
from telegram import Bot, Update
from telegram.ext import Dispatcher, MessageHandler, Filters, CommandHandler
import openai
from io import BytesIO
from PIL import Image
import logging

# Initialize Flask app
app = Flask(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize clients
bot = Bot(token=TELEGRAM_TOKEN)
openai.api_key = OPENAI_API_KEY

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook handler for Telegram"""
    if request.method == 'POST':
        update = Update.de_json(request.get_json(), bot)
        
        # Handle different types of updates
        if update.message:
            handle_message(update.message)
        elif update.callback_query:
            handle_callback(update.callback_query)
            
    return jsonify({'status': 'ok'})

def handle_message(message):
    """Handle incoming messages"""
    chat_id = message.chat.id
    
    try:
        # Check if message contains photo
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
        # Handle regular text messages
        welcome_text = """
🌿 *Plant Doctor Bot*

I can help you identify plant issues from photos! Here's how:

1. 📸 Take a clear photo of your plant's issue
2. 🖼️ Send the photo to me
3. 🔍 I'll analyze it using AI
4. 💡 Get diagnosis and treatment advice

*Available commands:*
/start - Show this welcome message
/help - Get help instructions
/analyze - Analyze a plant photo

Just send me a photo of your plant to get started!
        """
        bot.send_message(chat_id, welcome_text, parse_mode='Markdown')

def handle_commands(message):
    """Handle bot commands"""
    chat_id = message.chat.id
    text = message.text.strip().lower()
    
    if text == '/start' or text == '/help':
        welcome_text = """
🌱 *Welcome to Plant Doctor!*

I'm here to help diagnose your plant problems using AI.

*How to use:*
1. Take a clear photo of the affected plant part
2. Make sure the issue is visible (leaves, stems, etc.)
3. Send the photo directly to this chat
4. I'll analyze and provide recommendations

*Tips for better analysis:*
• Good lighting is important
• Focus on the affected areas
• Include both healthy and unhealthy parts if possible

Send me a plant photo now to get started! 📸
        """
        bot.send_message(chat_id, welcome_text, parse_mode='Markdown')
    
    elif text == '/analyze':
        bot.send_message(chat_id, "📸 Please send me a photo of your plant for analysis.")

def handle_plant_analysis(message):
    """Analyze plant photo using OpenAI"""
    chat_id = message.chat.id
    
    try:
        # Send processing message
        processing_msg = bot.send_message(chat_id, "🔍 Analyzing your plant photo...")
        
        # Get the highest quality photo
        photo_file = message.photo[-1].get_file()
        
        # Download photo
        photo_bytes = BytesIO()
        photo_file.download(out=photo_bytes)
        photo_bytes.seek(0)
        
        # Convert to base64 for OpenAI
        image_base64 = base64.b64encode(photo_bytes.getvalue()).decode('utf-8')
        
        # Analyze with OpenAI
        analysis = analyze_plant_with_openai(image_base64)
        
        # Delete processing message
        bot.delete_message(chat_id, processing_msg.message_id)
        
        # Send results
        send_analysis_results(chat_id, analysis)
        
    except Exception as e:
        logger.error(f"Error analyzing plant: {e}")
        bot.send_message(chat_id, "❌ Sorry, I couldn't analyze the image. Please try again with a clearer photo.")

def analyze_plant_with_openai(image_base64):
    """Use OpenAI to analyze plant issues"""
    
    prompt = """
Analyze this plant photo and provide a comprehensive diagnosis:

Please provide:
1. **Likely Issue**: What problem the plant might have
2. **Symptoms**: Visible signs in the photo
3. **Causes**: Possible reasons for the issue
4. **Treatment**: Step-by-step solutions
5. **Prevention**: How to avoid recurrence

Be specific and practical in your advice. If the image is unclear or doesn't show a plant, please indicate that.
"""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "I apologize, but I'm having trouble analyzing the image right now. Please try again with a clearer photo or contact a local gardening expert for immediate assistance."

def send_analysis_results(chat_id, analysis):
    """Send formatted analysis results to user"""
    
    # Format the response for better readability
    formatted_response = f"""
🌿 *Plant Analysis Results*

{analysis}

💡 *Remember*: This is an AI analysis. For serious plant issues, consider consulting a local gardening expert or agricultural extension service.

Send another photo if you have more plants to analyze!
"""
    
    # Split long messages if needed (Telegram has 4096 character limit)
    if len(formatted_response) > 4000:
        # Split into chunks
        chunks = [formatted_response[i:i+4000] for i in range(0, len(formatted_response), 4000)]
        for chunk in chunks:
            bot.send_message(chat_id, chunk, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, formatted_response, parse_mode='Markdown')

def handle_callback(callback_query):
    """Handle callback queries from inline keyboards"""
    chat_id = callback_query.message.chat.id
    query_data = callback_query.data
    
    bot.answer_callback_query(callback_query.id)
    bot.send_message(chat_id, "Feature coming soon!")

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Set webhook URL for Telegram"""
    webhook_url = os.getenv('WEBHOOK_URL')  # Your public URL
    if not webhook_url:
        return "WEBHOOK_URL environment variable not set", 400
    
    result = bot.set_webhook(webhook_url)
    if result:
        return f"Webhook set successfully: {webhook_url}"
    else:
        return "Failed to set webhook", 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'plant-doctor-bot'})

@app.route('/')
def home():
    """Home page"""
    return """
    <html>
        <head>
            <title>Plant Doctor Bot</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                .status { color: green; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🌿 Plant Doctor Bot</h1>
                <p>This bot helps diagnose plant issues using AI image analysis.</p>
                <p class="status">✅ Service is running</p>
                <p><strong>How it works:</strong></p>
                <ol>
                    <li>Users send photos of their plants</li>
                    <li>AI analyzes the image for issues</li>
                    <li>Bot provides diagnosis and treatment advice</li>
                </ol>
                <p><a href="https://t.me/YourBotUsername">Start using the bot</a></p>
            </div>
        </body>
    </html>
    """

if __name__ == '__main__':
    # For development
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)