import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

app = FastAPI()

# جلب البيانات من متغيرات البيئة في Render
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# إعداد نموذج Google Gemini بالاسم الصحيح والمتاح حالياً
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.3
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "أنت مساعد ذكي ومفيد تتحدث باللغة العربية."),
    ("user", "{input}")
])

chain = prompt | llm | StrOutputParser()

def send_whatsapp_message(to_number: str, message_text: str):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }
    requests.post(url, json=payload, headers=headers)

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(content=challenge, status_code=200)
    return PlainTextResponse(content="Verification failed", status_code=403)

@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    try:
        entries = data.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                if messages:
                    msg = messages[0]
                    from_number = msg.get("from")
                    text_body = msg.get("text", {}).get("body")

                    if text_body:
                        response_text = chain.invoke({"input": text_body})
                        send_whatsapp_message(from_number, response_text)
    except Exception as e:
        print(f"Error handling webhook: {e}")

    return {"status": "ok"}
