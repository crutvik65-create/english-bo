import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from gtts import gTTS
import tempfile
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - Load from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)

# Store user data
user_contexts = {}
user_stats = {}

# Enhanced system prompt for natural human-like conversation
SYSTEM_PROMPT = """You are a friendly, warm English conversation partner named Alex. You talk like a real human friend - casual, natural, and engaging.

**YOUR PERSONALITY:**
- Talk exactly like you're texting a friend - natural and relaxed
- Use contractions heavily (I'm, you're, that's, don't, can't, won't)
- Use casual expressions: "Oh wow!", "That's awesome!", "I feel you", "For sure!"
- Be enthusiastic and genuinely interested
- Keep it SHORT and punchy - like real human conversation
- Use emoji occasionally for warmth 😊

**RESPONSE FORMAT:**
Your response MUST follow this structure:

[CONVERSATION]
<Your super natural, friendly response - 2-3 short sentences that sound exactly like a human texting>

[ANALYSIS]
**What you said:** "<repeat their exact words>"
**Corrections:**
- Grammar: [List any grammar errors with corrections]
- Vocabulary: [Suggest better word choices if needed]
- Pronunciation tip: [Mention any tricky words they used]

**Better way to say it:**
"<Provide corrected version>"

**CONVERSATION STYLE EXAMPLES:**
❌ BAD: "That sounds very interesting. I would like to know more about it."
✅ GOOD: "Oh that's cool! Tell me more about it!"

❌ BAD: "I understand your situation. It must be difficult."
✅ GOOD: "I totally get it. That sounds tough!"

❌ BAD: "Thank you for sharing that information with me."
✅ GOOD: "Thanks for sharing! That's really interesting!"

**RULES:**
- Sound like a real human, not a robot or teacher
- Keep conversation parts SHORT (2-3 sentences max)
- Use natural fillers: "I mean", "You know", "Like"
- If NO mistakes: just say "✓ Perfect! No corrections needed."
- Be encouraging but casual
- Match their energy level

**Example:**
User: "I am going to market yesterday"

Your response:
[CONVERSATION]
Oh nice! Shopping is always fun. What'd you end up buying? 

[ANALYSIS]
**What you said:** "I am going to market yesterday"
**Corrections:**
- Grammar: Use "went" (past) not "am going" (present) with "yesterday"
- Article: Add "the" → "the market"

**Better way to say it:**
"I went to the market yesterday"

**Pronunciation tip:** 
- "market" = MAR-ket"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued"""
    user_id = update.effective_user.id
    user_contexts[user_id] = []
    user_stats[user_id] = {"messages": 0, "mistakes_found": 0}
    
    welcome_text = """👋 **Hey! I'm Alex, your English chat buddy!**

Let's just chat naturally and I'll help you improve your English along the way.

🎯 **What I do:**
✓ Chat with you like a real friend would
✓ Gently point out grammar mistakes
✓ Help with pronunciation
✓ Suggest better ways to say things
✓ Keep it fun and casual!

🎤 **How it works:**
1. Send me a voice message or text
2. I'll respond naturally (with voice!)
3. I'll also give you quick feedback on your English
4. We just keep chatting!

📝 **Commands:**
/start - This message
/reset - Start fresh
/tips - Get learning tips
/stats - See your progress

**Ready? Just send me a message! Tell me what you did today!** 🚀"""
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')


async def reset_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset conversation history"""
    user_id = update.effective_user.id
    user_contexts[user_id] = []
    await update.message.reply_text("✨ Cool! Fresh start. So what's up? What do you wanna chat about?")


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user statistics"""
    user_id = update.effective_user.id
    stats = user_stats.get(user_id, {"messages": 0, "mistakes_found": 0})
    
    stats_text = f"""📊 **Your Progress:**

💬 Messages: {stats['messages']}
❌ Mistakes found: {stats['mistakes_found']}
✅ Improvement: {max(0, 100 - (stats['mistakes_found'] * 10))}%

You're doing awesome! Keep it up! 🌟"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')


async def tips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provide general pronunciation and grammar tips"""
    tips_text = """📚 **English Tips:**

**🗣️ Speaking:**
1. Don't rush - clear is better than fast
2. Record yourself and listen back
3. Watch English shows and copy them
4. Practice every day, even just 5 mins!
5. Mistakes are totally fine - that's how you learn!

**📖 Common Mistakes:**

❌ "I am having two brothers"
✅ "I have two brothers"

❌ "She is more taller"
✅ "She is taller"

❌ "I didn't went"
✅ "I didn't go"

❌ "He don't like"
✅ "He doesn't like"

**🎯 Tricky Words:**
- Through (throo)
- Thought (thawt)
- Though (thoh)
- Colonel (KER-nel)
- Receipt (rih-SEET)

**Just keep chatting with me! 🚀**"""
    
    await update.message.reply_text(tips_text, parse_mode='Markdown')


async def transcribe_audio(file_path: str) -> str:
    """Transcribe audio using Groq Whisper"""
    try:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        
        with open(file_path, "rb") as audio_file:
            files = {"file": (os.path.basename(file_path), audio_file, "audio/ogg")}
            data = {
                "model": "whisper-large-v3-turbo",
                "language": "en",
                "response_format": "json"
            }
            response = requests.post(url, headers=headers, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("text", "").strip()
            else:
                logger.error(f"Transcription error: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return None


async def get_ai_response(user_id: int, user_text: str) -> dict:
    """Get AI response with natural human-like analysis"""
    try:
        if user_id not in user_contexts:
            user_contexts[user_id] = []
        
        # Add user message
        user_contexts[user_id].append({"role": "user", "content": user_text})
        
        # Keep last 10 messages
        if len(user_contexts[user_id]) > 10:
            user_contexts[user_id] = user_contexts[user_id][-10:]
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + user_contexts[user_id]
        
        # Get response from Groq
        chat_completion = groq_client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.9,  # Higher for more natural/human responses
            max_tokens=500,
            top_p=0.95
        )
        
        ai_response = chat_completion.choices[0].message.content
        
        # Add to context
        user_contexts[user_id].append({"role": "assistant", "content": ai_response})
        
        # Parse response
        conversation_part = ""
        analysis_part = ""
        
        if "[CONVERSATION]" in ai_response and "[ANALYSIS]" in ai_response:
            parts = ai_response.split("[ANALYSIS]")
            conversation_part = parts[0].replace("[CONVERSATION]", "").strip()
            analysis_part = parts[1].strip()
        else:
            conversation_part = ai_response
            analysis_part = ""
        
        # Update stats
        if user_id not in user_stats:
            user_stats[user_id] = {"messages": 0, "mistakes_found": 0}
        user_stats[user_id]["messages"] += 1
        if analysis_part and "No corrections needed" not in analysis_part:
            user_stats[user_id]["mistakes_found"] += 1
        
        return {
            "conversation": conversation_part,
            "analysis": analysis_part,
            "full_response": ai_response
        }
        
    except Exception as e:
        logger.error(f"AI error: {e}")
        return {
            "conversation": "Oops, something's acting up. Can you try again?",
            "analysis": "",
            "full_response": "Oops, something's acting up. Can you try again?"
        }


async def text_to_speech_enhanced(text: str) -> str:
    """Convert text to speech using enhanced gTTS (free and decent quality)"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            output_file = fp.name
        
        # Using gTTS with optimized settings for more natural sound
        tts = gTTS(
            text=text, 
            lang='en', 
            slow=False,
            tld='com'  # US accent
        )
        tts.save(output_file)
        
        return output_file
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages"""
    try:
        user_id = update.effective_user.id
        
        await update.message.chat.send_action(action="typing")
        
        # Download voice
        voice_file = await update.message.voice.get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_audio:
            await voice_file.download_to_drive(temp_audio.name)
            audio_path = temp_audio.name
        
        # Transcribe
        await update.message.reply_text("🎧 Listening...")
        transcribed_text = await transcribe_audio(audio_path)
        
        if not transcribed_text:
            await update.message.reply_text("Hmm, couldn't catch that. Try again?")
            os.unlink(audio_path)
            return
        
        # Show what they said
        await update.message.reply_text(f"📝 **You said:**\n_{transcribed_text}_", parse_mode='Markdown')
        
        # Get AI response
        await update.message.chat.send_action(action="typing")
        ai_result = await get_ai_response(user_id, transcribed_text)
        
        # Send text response
        conversation_text = f"💬 **Alex:**\n{ai_result['conversation']}"
        await update.message.reply_text(conversation_text, parse_mode='Markdown')
        
        # Generate voice response
        await update.message.chat.send_action(action="record_voice")
        audio_file = await text_to_speech_enhanced(ai_result['conversation'])
        
        if audio_file:
            with open(audio_file, 'rb') as audio:
                await update.message.reply_voice(voice=audio)
            os.unlink(audio_file)
        
        # Send analysis
        if ai_result['analysis']:
            analysis_text = f"📊 **Quick Feedback:**\n\n{ai_result['analysis']}"
            await update.message.reply_text(analysis_text, parse_mode='Markdown')
        
        os.unlink(audio_path)
        
    except Exception as e:
        logger.error(f"Voice error: {e}")
        await update.message.reply_text("❌ Something went wrong! Try again?")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    try:
        user_id = update.effective_user.id
        user_text = update.message.text
        
        await update.message.chat.send_action(action="typing")
        
        # Get AI response
        ai_result = await get_ai_response(user_id, user_text)
        
        # Send text
        conversation_text = f"💬 **Alex:**\n{ai_result['conversation']}"
        await update.message.reply_text(conversation_text, parse_mode='Markdown')
        
        # Generate voice
        await update.message.chat.send_action(action="record_voice")
        audio_file = await text_to_speech_enhanced(ai_result['conversation'])
        
        if audio_file:
            with open(audio_file, 'rb') as audio:
                await update.message.reply_voice(voice=audio)
            os.unlink(audio_file)
        
        # Send analysis
        if ai_result['analysis']:
            analysis_text = f"📊 **Quick Feedback:**\n\n{ai_result['analysis']}"
            await update.message.reply_text(analysis_text, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Text error: {e}")
        await update.message.reply_text("❌ Oops! Try that again?")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot"""
    if not TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_TOKEN not found in .env file!")
        return
    
    if not GROQ_API_KEY:
        print("❌ Error: GROQ_API_KEY not found in .env file!")
        return
    
    print("🤖 Starting Natural English Chat Bot...")
    print("🎤 Voice: Google TTS (Free)")
    print("💡 AI Model: Llama 3.3 70B (Human-like responses)")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_conversation))
    application.add_handler(CommandHandler("tips", tips))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(error_handler)
    
    print("✅ Bot running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()