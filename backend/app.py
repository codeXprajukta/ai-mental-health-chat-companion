# backend/app.py
import datetime, uuid, sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk, uvicorn

# Ensure VADER lexicon is available
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    nltk.download("vader_lexicon")

app = FastAPI(title="AI Mental Health Companion")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sid = SentimentIntensityAnalyzer()

# --------------------------
# Database (SQLite for history)
# --------------------------
DB_FILE = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS history (
        user_id TEXT,
        timestamp TEXT,
        user_msg TEXT,
        bot_msg TEXT,
        emotion TEXT,
        confidence REAL,
        escalate INTEGER
    )
    """)
    conn.commit()
    conn.close()

init_db()

# --------------------------
# Data Models
# --------------------------
class MessageIn(BaseModel):
    user_id: str | None = None
    text: str

class MessageOut(BaseModel):
    user_id: str
    text: str
    emotion: str
    confidence: float
    escalate: bool
    suggestion: str | None
    timestamp: str

# --------------------------
# Suggestions
# --------------------------
SUGGESTIONS = {
    "anger": "Try deep breathing: inhale 4s, hold 4s, exhale 6s.",
    "sadness": "Write down 3 small positives today, no matter how small.",
    "fear": "Ground yourself: Name 5 things you see, 4 you touch, 3 you hear.",
    "joy": "Celebrate! Capture this moment in a note or photo.",
    "stress": "Stretch for 2 minutes or drink a glass of water.",
    "calm": "Enjoy the calm — maybe play soothing music.",
    "severe_distress": "Reach out immediately to a trusted friend or hotline."
}

# --------------------------
# Emotion Detection
# --------------------------
def detect_emotion(text: str):
    scores = sid.polarity_scores(text)
    compound = scores["compound"]
    lw = text.lower()
    escalate = False
    emotion, conf = "neutral", 0.5

    if any(w in lw for w in ["suicid", "kill myself", "end my life", "want to die", "harm myself"]):
        return "severe_distress", 1.0, True

    if "angry" in lw or "furious" in lw or "hate" in lw:
        emotion, conf = "anger", abs(compound)
    elif "anxious" in lw or "panic" in lw or "fear" in lw:
        emotion, conf = "fear", abs(compound)
    elif "sad" in lw or "depressed" in lw or "hopeless" in lw:
        emotion, conf = "sadness", abs(compound)
    elif compound >= 0.6:
        emotion, conf = "joy", compound
    elif compound <= -0.6:
        emotion, conf = "sadness", abs(compound)
    elif compound < -0.3:
        emotion, conf = "stress", abs(compound)
    elif compound > 0.3:
        emotion, conf = "calm", compound

    if compound <= -0.7:
        escalate = True

    return emotion, conf, escalate

def generate_response(emotion: str, escalate: bool):
    if escalate or emotion == "severe_distress":
        return ("⚠️ I'm really concerned about your safety. "
                "Please call emergency services or a suicide hotline now. "
                "You’re not alone.")
    if emotion == "anger":
        return "I hear your anger. Let’s breathe together slowly."
    if emotion == "sadness":
        return "I’m sorry you’re feeling sad. Want to talk about it?"
    if emotion == "fear":
        return "That sounds frightening — let’s try a grounding exercise."
    if emotion == "joy":
        return "That’s amazing! What made you happy?"
    if emotion == "stress":
        return "I sense stress. Let’s break it into small steps."
    if emotion == "calm":
        return "That’s wonderful — enjoy this calm moment."
    return "Thanks for sharing. I’m listening."

# --------------------------
# API Endpoints
# --------------------------
@app.post("/api/chat", response_model=MessageOut)
def chat(msg: MessageIn):
    if not msg.text.strip():
        raise HTTPException(status_code=400, detail="Text is empty")

    user_id = msg.user_id or str(uuid.uuid4())
    emotion, confidence, escalate = detect_emotion(msg.text)
    reply = generate_response(emotion, escalate)
    suggestion = SUGGESTIONS.get(emotion)

    ts = datetime.datetime.utcnow().isoformat() + "Z"

    # Save to DB
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES (?,?,?,?,?,?,?)",
              (user_id, ts, msg.text, reply, emotion, confidence, int(escalate)))
    conn.commit()
    conn.close()

    return {
        "user_id": user_id,
        "text": reply,
        "emotion": emotion,
        "confidence": confidence,
        "escalate": escalate,
        "suggestion": suggestion,
        "timestamp": ts,
    }

@app.get("/api/history/{user_id}")
def get_history(user_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT timestamp, user_msg, bot_msg, emotion FROM history WHERE user_id=? ORDER BY timestamp", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{"timestamp": r[0], "user": r[1], "bot": r[2], "emotion": r[3]} for r in rows]

@app.get("/api/stats/{user_id}")
def get_stats(user_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT emotion, COUNT(*) FROM history WHERE user_id=? GROUP BY emotion", (user_id,))
    rows = c.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}
    
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
