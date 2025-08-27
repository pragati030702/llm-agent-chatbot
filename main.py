from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import re
import math

app = FastAPI()

# Serve static files (frontend)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    message = data.get("message", "").lower().strip()

    response = "I'm not sure how to answer that yet."

    # Weather query (demo response)
    if message.startswith("weather in"):
        city = message.replace("weather in", "").strip().title()
        response = f"☁️ The weather in {city} is currently sunny (demo response)."

    # Simple calculator
    elif message.startswith("calc"):
        expr = message.replace("calc", "").strip()
        try:
            result = eval(expr, {"__builtins__": {}}, math.__dict__)
            response = f"🧮 Result: {result}"
        except:
            response = "⚠️ Sorry, I couldn’t calculate that."

    # Small talk
    elif "hello" in message or "hi" in message:
        response = "👋 Hello! How can I help you today?"

    elif "your name" in message:
        response = "🤖 I'm your FastAPI chatbot!"

    return JSONResponse({"response": response})
