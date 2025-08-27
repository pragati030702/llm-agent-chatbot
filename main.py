from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import os, re, requests
from dotenv import load_dotenv

# -------------------------------
# Load environment variables
# -------------------------------
load_dotenv()
USE_OPENAI = os.getenv("USE_OPENAI", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

app = FastAPI(title="FastAPI Chatbot")

# -------------------------------
# HTML UI
# -------------------------------
HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FastAPI Chatbot</title>
  <style>
    body { font-family: system-ui, Arial, sans-serif; margin: 0; background:#0b1220; color:#e6eefc; }
    header { padding: 18px 22px; background: #0f1629; border-bottom: 1px solid #1e2a44; }
    main { max-width: 860px; margin: 0 auto; padding: 20px; }
    .bubble { padding: 12px 14px; border-radius: 12px; margin: 8px 0; max-width: 80%; line-height:1.4 }
    .me { background:#254; align-self:flex-end; margin-left:auto; }
    .bot { background:#1b2540; border:1px solid #27375f; }
    .row { display:flex; gap:10px; margin-top:14px; }
    textarea { flex:1; min-height:64px; resize:vertical; background:#0f1629; color:#e6eefc; border:1px solid #27375f; border-radius:10px; padding:10px; }
    button { padding:12px 16px; border:0; background:#3b82f6; color:white; border-radius:10px; cursor:pointer; }
    button:disabled{ opacity:.6; cursor:not-allowed; }
    .log { display:flex; flex-direction:column; gap:4px; margin-top:12px; }
    .hint { color:#9fb3d9; font-size: 0.9rem; margin-top:8px; }
    a { color:#9cc1ff; }
  </style>
</head>
<body>
  <header><strong>FastAPI Chatbot</strong></header>
  <main>
    <div class="hint">Try: <code>weather in London</code> or ask anything.</div>
    <div id="log" class="log"></div>
    <div class="row">
      <textarea id="input" placeholder="Type a message..."></textarea>
      <button id="send">Send</button>
    </div>
  </main>
  <script>
    const elLog = document.getElementById('log');
    const elInput = document.getElementById('input');
    const elSend = document.getElementById('send');

    function addBubble(text, cls) {
      const div = document.createElement('div');
      div.className = 'bubble ' + cls;
      div.textContent = text;
      elLog.appendChild(div);
      div.scrollIntoView({behavior:'smooth', block:'end'});
    }

    async function send() {
      const msg = elInput.value.trim();
      if (!msg) return;
      elInput.value = '';
      addBubble(msg, 'me');
      elSend.disabled = true;
      try {
        const res = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg })
        });
        const data = await res.json();
        addBubble(data.reply || 'No reply', 'bot');
      } catch (e) {
        addBubble('Error contacting server.', 'bot');
      } finally {
        elSend.disabled = false;
      }
    }

    elSend.addEventListener('click', send);
    elInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });

    addBubble("Hi! I'm your FastAPI bot. Ask me the weather: e.g., 'weather in Paris'.", 'bot');
  </script>
</body>
</html>
"""

# -------------------------------
# Data models
# -------------------------------
class ChatRequest(BaseModel):
    message: str

# -------------------------------
# Helper functions
# -------------------------------
def extract_city(text: str) -> str | None:
    m = re.search(r"weather\s+(?:in|at|for)\s+([a-zA-Z\s'.-]{2,})", text, re.IGNORECASE)
    if m: return m.group(1).strip()
    m = re.search(r"\b(?:in|at)\s+([A-Za-z\s'.-]{2,})\b", text, re.IGNORECASE)
    if m and 'weather' in text.lower(): return m.group(1).strip()
    return None

def fetch_weather(city: str) -> str | None:
    try:
        g = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=8
        ).json()
        if not g.get("results"):
            return None
        r = g["results"][0]
        lat, lon, name, country = r["latitude"], r["longitude"], r["name"], r.get("country", "")
        f = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True, "timezone": "auto"},
            timeout=8
        ).json()
        cw = f.get("current_weather") or {}
        if not cw:
            return None
        temp = cw.get("temperature")
        wind = cw.get("windspeed")
        weathercode = cw.get("weathercode")
        # Minimal mapping for nicer text
        code_map = {
            0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "fog", 48: "depositing rime fog",
            51: "light drizzle", 53: "drizzle", 55: "dense drizzle",
            61: "light rain", 63: "rain", 65: "heavy rain",
            71: "light snow", 73: "snow", 75: "heavy snow",
            80: "rain showers", 81: "heavy rain showers", 82: "violent rain showers",
        }
        cond = code_map.get(int(weathercode or -1), "conditions available")
        return f"Weather for {name}, {country}: {temp}°C, {cond}, wind {wind} km/h."
    except Exception:
        return None

def call_openai(prompt: str) -> str:
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20
        ).json()
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return "Error calling OpenAI API."

# -------------------------------
# Routes
# -------------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

@app.post("/chat")
def chat(req: ChatRequest):
    text = req.message.strip()

    # Weather first
    city = extract_city(text)
    if city:
        w = fetch_weather(city)
        if w:
            return JSONResponse({"reply": w})

    # OpenAI path (optional, only if enabled)
    if USE_OPENAI and OPENAI_API_KEY:
        ai_reply = call_openai(text)
        return JSONResponse({"reply": ai_reply})

    # Fallback simple replies
    if re.search(r"\b(hi|hello|hey)\b", text, re.I):
        return JSONResponse({"reply": "Hey! Ask me for the weather: e.g., 'weather in Tokyo'."})
    if re.search(r"\bhelp\b", text, re.I):
        return JSONResponse({"reply": "I can fetch current weather via Open-Meteo. Try 'weather in <city>'."})
    return JSONResponse({"reply": "Got it! (Tip: try 'weather in Berlin')"})
