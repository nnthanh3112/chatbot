from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import AzureOpenAI
import os
import json
import markdown2
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

app = FastAPI()

# Static & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Azure OpenAI config
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT").strip('"')
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY").strip('"')
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT").strip('"')
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION").strip('"')

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)

# Azure Cognitive Search config
AZURE_SEARCH_SERVICE_NAME = os.getenv("AZURE_SEARCH_SERVICE_NAME").strip('"')
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME").strip('"')
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY").strip('"')

# PostgreSQL setup
#DATABASE_URL = os.getenv("DATABASE_URL").strip('"')
DATABASE_URL = os.getenv("DATABASE_URL").strip('"')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models for Database (Lưu lịch sử chat vào PostgreSQL)
class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_message = Column(String, index=True)
    assistant_message = Column(String)

# Create the database tables
Base.metadata.create_all(bind=engine)

@app.get("/", response_class=HTMLResponse)
async def chat_interface(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/chat")
async def chat_api(request: Request, query: str = Form(...), history: str = Form("")):
    # Prepare messages with the system and history if it exists
    messages = [{"role": "system", "content": "Bạn là một trợ lý AI thông minh."}]
    
    if history:
        messages += json.loads(history)  # Add previous chat history

    messages.append({"role": "user", "content": query})

    try:
        # Make API call to Azure OpenAI
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=0.7,
            max_tokens=800
        )

        raw_answer = response.choices[0].message.content.strip()
        answer_html = markdown2.markdown(raw_answer)


        # Chuyển đổi thẻ <br/> vào mỗi dòng trong câu trả lời để xuống dòng
        answer_html = answer_html.replace("\n", "<br/>")

        # Save chat history into PostgreSQL database
        db = SessionLocal()
        chat_history = ChatHistory(
            user_message=query,
            assistant_message=raw_answer
        )
        db.add(chat_history)
        db.commit()
        db.refresh(chat_history)
        db.close()

        # Find citations if any
        citations = []
        if response.choices[0].message.tool_calls:
            arguments = response.choices[0].message.tool_calls[0].function.arguments
            citations = arguments.get("citations", [])

        if citations:
            ref_list_html = "<p><strong>Tài liệu tham khảo:</strong></p><ul>"
            for idx, ref in enumerate(citations, start=1):
                title = ref.get("content", f"Tài liệu {idx}")
                ref_list_html += f"<li>[{idx}] {title}</li>"
            ref_list_html += "</ul>"
            answer_html += ref_list_html

    except Exception as e:
        answer_html = f"Lỗi từ OpenAI API: {str(e)}"

    # Add assistant response to the chat history
    messages.append({"role": "assistant", "content": answer_html})

    # Return answer and updated history to frontend
    return JSONResponse(content={"answer": answer_html, "history": messages})

@app.get("/history", response_class=JSONResponse)
async def get_history():
    # Get all chat history from PostgreSQL
    db = SessionLocal()
    history = db.query(ChatHistory).all()
    db.close()

    # Format chat history to return as JSON
    history_data = [{"user_message": record.user_message, "assistant_message": record.assistant_message} for record in history]
    return {"history": history_data}
