import os
import csv
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
import uuid
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Flask app initialization
app = Flask(__name__)
CORS(app)

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    db = client["chat_history"]
    collection = db["chats"]
    collection.create_index("session_id", unique=True)
    collection.create_index("timestamp")
except Exception as e:
    print(f"[⚠️] MongoDB connection warning: {e}")

# Set your Gemini API Key from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Configure Gemini API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Load Knowledge Base from CSV
KNOWLEDGE_BASE = []
KB_PATH = os.path.join(os.path.dirname(__file__), "electronics_tools_knowledge_base.csv")

def load_knowledge_base():
    global KNOWLEDGE_BASE
    KNOWLEDGE_BASE = []
    if os.path.exists(KB_PATH):
        try:
            with open(KB_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    q = row.get("question", "").strip()
                    a = row.get("answer", "").strip()
                    if q and a:
                        KNOWLEDGE_BASE.append({"question": q, "answer": a})
            print(f"[✅] Loaded {len(KNOWLEDGE_BASE)} entries into Knowledge Base.")
        except Exception as e:
            print(f"[❌] Error loading Knowledge Base: {e}")

load_knowledge_base()

def search_knowledge_base(text):
    """Search knowledge base for relevant Q&A matches based on word overlap"""
    if not KNOWLEDGE_BASE:
        return None
    
    text_clean = set(text.lower().replace("?", "").replace(".", "").split())
    query_words = {w for w in text_clean if len(w) > 2}
    
    best_match = None
    best_score = 0
    
    for item in KNOWLEDGE_BASE:
        q_words = set(item["question"].lower().replace("?", "").replace(".", "").split())
        q_meaningful = {w for w in q_words if len(w) > 2}
        
        if not q_meaningful:
            continue
            
        intersection = query_words.intersection(q_meaningful)
        score = len(intersection) / len(q_meaningful)
        
        if score > best_score and len(intersection) >= 2:
            best_score = score
            best_match = item["answer"]
            
    if best_score >= 0.5:
        return best_match
    return None

# Function to check if user is asking about AI identity
def is_identity_question(text):
    """Check if the user is asking about the AI's identity"""
    text_lower = text.lower().strip()
    identity_keywords = [
        "who are you",
        "what are you",
        "what is your name",
        "who is aura",
        "tell me about yourself",
        "introduce yourself"
    ]
    return any(keyword in text_lower for keyword in identity_keywords)


# Function to check if user is giving a simple compliment or acknowledgment
def is_simple_compliment(text):
    """Check if the user is giving a simple compliment that should get a brief response"""
    text_lower = text.lower().strip()
    text_clean = ''.join(c for c in text_lower if c.isalnum() or c.isspace())
    
    simple_compliments = [
        "good", "well done", "welldone", "nice", "great", "excellent",
        "perfect", "thanks", "thank you", "ok", "okay", "alright", "sure",
        "yes", "yeah", "yep", "no", "nope", "bye", "goodbye", "hi", "hello", "hey"
    ]
    
    words = text_clean.split()
    if len(words) <= 2:
        for compliment in simple_compliments:
            if compliment == text_clean or compliment in text_clean:
                return True
    return False


# Function to get appropriate response for simple compliments
def get_compliment_response(text):
    """Get a brief, friendly response for simple compliments"""
    text_lower = text.lower().strip()
    text_clean = ''.join(c for c in text_lower if c.isalnum() or c.isspace())
    
    if any(word in text_clean for word in ["good", "well done", "welldone", "nice", "great", "excellent", "perfect"]):
        return "Thank you! I'm glad I could help."
    elif any(word in text_clean for word in ["thanks", "thank you"]):
        return "You're welcome! Happy to help."
    elif any(word in text_clean for word in ["ok", "okay", "alright", "sure", "yes", "yeah", "yep"]):
        return "Great! How can I assist you?"
    elif any(word in text_clean for word in ["no", "nope"]):
        return "Understood. What would you like to know?"
    elif any(word in text_clean for word in ["bye", "goodbye"]):
        return "Goodbye! Feel free to come back anytime."
    elif any(word in text_clean for word in ["hi", "hello", "hey"]):
        return "Hello! I'm AURA, your AI voice assistant. How can I help you today?"
    else:
        return "Thank you!"


# Function to generate a chat title from the first user message (2-3 words)
def generate_chat_title(text):
    """Generate a 2-3 word title from the user's message"""
    text_clean = ' '.join(text.split())
    words = text_clean.split()
    
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being", 
                  "have", "has", "had", "do", "does", "did", "will", "would", "could", 
                  "should", "may", "might", "must", "can", "what", "when", "where", 
                  "who", "why", "how", "this", "that", "these", "those", "i", "you", 
                  "he", "she", "it", "we", "they", "me", "him", "her", "us", "them"}
    
    meaningful_words = [w.lower() for w in words if w.lower() not in stop_words and len(w) > 2]
    
    if meaningful_words:
        title_words = meaningful_words[:3]
    else:
        title_words = words[:3]
    
    title = ' '.join(word.capitalize() for word in title_words if word)
    if not title or len(title) < 3:
        title = ' '.join(words[:3]).capitalize()
    
    return title if title else "New Chat"


# Function to get response from Gemini with structured formatting
def get_gemini_response(prompt, context=None):
    # Models to try in order of preference
    models_to_try = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-2.5-flash"]
    
    context_instruction = f"\nUse this verified technical knowledge if relevant: {context}\n" if context else ""
    
    structured_prompt = f"""You are AURA, an AI voice assistant. Provide a well-structured, organized, and comprehensive answer to the following question.
{context_instruction}
Format your response using markdown with:
- **Bold text** for key terms, important concepts, and section headings
- ## or ### for main section headings
- Bullet points (- or •) for lists of items
- Numbered lists (1., 2., 3.) for sequential information
- Clear paragraphs with proper spacing between sections
- Keep the structure clean and easy to read

Question: {prompt}

Provide a detailed, structured response:"""

    last_error = None
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(structured_prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            last_error = e
            continue

    # Fallback to direct Knowledge Base answer if AI model failed or unreachable
    if context:
        return f"**Knowledge Base Answer:**\n\n{context}"
        
    return f"I couldn't reach the AI model right now. (Error: {str(last_error)})"


# ➕ Route to create a new chat session
@app.route("/new_chat", methods=["POST"])
def new_chat():
    session_id = str(uuid.uuid4())
    chat_data = {
        "session_id": session_id,
        "chat": [],
        "timestamp": datetime.now()
    }
    try:
        collection.insert_one(chat_data)
    except Exception as e:
        print(f"[⚠️] Could not save new chat session to MongoDB: {e}")
    return jsonify({"session_id": session_id})


# 🚀 Route to process chat messages
@app.route("/process", methods=["POST"])
def process():
    data = request.json
    text = data.get("text", "")
    session_id = data.get("session_id", "")

    if not session_id or not text:
        return jsonify({"error": "Invalid request"}), 400

    # Check if user is asking about AI identity
    if is_identity_question(text):
        bot_response = "I am AURA, your AI voice assistant. How can I assist you today?"
    # Check if user is giving a simple compliment or acknowledgment
    elif is_simple_compliment(text):
        bot_response = get_compliment_response(text)
    else:
        # Search Knowledge Base for domain context
        kb_context = search_knowledge_base(text)
        # Get AI response with context fallback
        bot_response = get_gemini_response(text, context=kb_context)

    # Store the conversation in MongoDB if available
    try:
        chat_doc = collection.find_one({"session_id": session_id})
        is_first_message = chat_doc and len(chat_doc.get("chat", [])) == 0
        
        update_data = {
            "$push": {
                "chat": {
                    "$each": [
                        {"sender": "user", "text": text},
                        {"sender": "bot", "text": bot_response}
                    ]
                }
            }
        }
        
        if is_first_message:
            title = generate_chat_title(text)
            update_data["$set"] = {"title": title}
        
        collection.update_one(
            {"session_id": session_id},
            update_data
        )
    except Exception as e:
        print(f"[⚠️] Could not update chat history in MongoDB: {e}")

    return jsonify({"bot_response": bot_response})


# 🔥 Route to get all previous chats (optimized - returns only metadata)
@app.route("/chats", methods=["GET"])
def get_chats():
    try:
        pipeline = [
            {
                "$project": {
                    "_id": 0,
                    "session_id": 1,
                    "timestamp": 1,
                    "title": 1,
                    "message_count": {"$size": "$chat"}
                }
            },
            {"$sort": {"timestamp": -1}}  # Sort by newest first
        ]
        chats = list(collection.aggregate(pipeline))
        for chat in chats:
            if not chat.get("title"):
                chat["title"] = "New Chat"
        return jsonify(chats)
    except Exception as e:
        print(f"[⚠️] Could not fetch chats from MongoDB: {e}")
        return jsonify([])


# 📖 Route to get full chat history for a specific session
@app.route("/chat/<session_id>", methods=["GET"])
def get_chat(session_id):
    try:
        chat = collection.find_one(
            {"session_id": session_id},
            {"_id": 0, "chat": 1, "timestamp": 1}
        )
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
        return jsonify({
            "chat": chat.get("chat", []),
            "timestamp": chat.get("timestamp")
        })
    except Exception as e:
        print(f"[⚠️] Could not fetch chat {session_id} from MongoDB: {e}")
        return jsonify({"chat": [], "error": str(e)}), 500


# 💾 Route to save chat (chats are auto-saved, but this endpoint exists for compatibility)
@app.route("/save_chat", methods=["POST"])
def save_chat():
    return jsonify({"message": "Chat saved"}), 200


# 🗑️ Route to delete a specific chat
@app.route("/delete_chat", methods=["POST"])
def delete_chat():
    session_id = request.json.get("session_id")
    if not session_id:
        return jsonify({"error": "No session ID provided"}), 400

    try:
        result = collection.delete_one({"session_id": session_id})
        if result.deleted_count == 1:
            return jsonify({"message": "Chat deleted successfully"}), 200
        else:
            return jsonify({"error": "Chat not found"}), 404
    except Exception as e:
        print(f"[⚠️] Could not delete chat from MongoDB: {e}")
        return jsonify({"error": str(e)}), 500


# ➡️ Main entry point
if __name__ == "__main__":
    print("[✅] AURA Voice Assistant Running...")
    app.run(debug=True, use_reloader=False)
