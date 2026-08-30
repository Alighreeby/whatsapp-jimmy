import os
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response, JSONResponse
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

app = FastAPI(title="WhatsApp AI Technical Agent")

# المفاتيح الحساسة يتم سحبها تلقائياً من بيئة الخادم
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "LY_TECH_SECRET_2026")

DB_URL = os.getenv("DATABASE_URL", "sqlite:///chat_history.db")

llm = ChatOpenAI(model="gpt-4o", temperature=0.2)

prompt = ChatPromptTemplate.from_messages([
    ("system", """أنت خبير تقني شامل ومساعد برمجيات وحسابات عبر واتساب.
    تذكر جميع الأسئلة والأكواد والحلول السابقة للمستخدم والواردة في سجل المحادثة.
    عندما يسألك المستخدم عن أمر سابق (مثل: "ما هو الكود الذي كتبته لي سابقاً؟") قم بالرجوع للذاكرة وإجابته فوراً."""),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

chain = prompt | llm

def get_session_history(session_id: str):
    return SQLChatMessageHistory(session_id=session_id, connection_string=DB_URL)

agent_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

def send_whatsapp_message(to: str, message_text: str):
    if not PHONE_NUMBER_ID or not WHATSAPP_TOKEN:
        print("خطأ: مفاتيح Meta غير متوفرة.")
        return

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message_text}
    }
    requests.post(url, json=payload, headers=headers)

def process_tech_query(user_phone: str, user_message: str):
    try:
        config = {"configurable": {"session_id": user_phone}}
        response = agent_with_history.invoke({"input": user_message}, config=config)
        send_whatsapp_message(user_phone, response.content)
    except Exception as e:
        print(f"خطأ في معالجة الطلب والذاكرة: {e}")

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge"), status_code=200)
    return Response(content="Verification failed", status_code=403)

@app.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        entry = data['entry'][0]['changes'][0]['value']
        if 'messages' in entry:
            message = entry['messages'][0]
            user_phone = message['from']
            if message.get('type') == 'text':
                user_message = message['text']['body']
                background_tasks.add_task(process_tech_query, user_phone, user_message)
    except Exception as e:
        print(f"خطأ أثناء استقبال الرسالة: {e}")

    return JSONResponse(content={"status": "success"}, status_code=200)
