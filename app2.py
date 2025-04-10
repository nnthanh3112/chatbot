from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
import os
import json
import markdown2

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Azure OpenAI config
AZURE_OPENAI_ENDPOINT = "https://eastus.api.cognitive.microsoft.com/"
AZURE_OPENAI_API_KEY = "fe365a10250646b5a5d608df5180745b"
AZURE_OPENAI_DEPLOYMENT = "gpt-4-turbo"
AZURE_OPENAI_API_VERSION = "2025-01-01-preview"

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)

# Azure Cognitive Search config
search_service_name = "azure-document-search"
search_index_name = "realestate-us-sample-index"
search_api_key = os.getenv("AZURE_SEARCH_API_KEY", "")

search_client = SearchClient(
    endpoint=f"https://{search_service_name}.search.windows.net",
    index_name=search_index_name,
    credential=AzureKeyCredential(search_api_key),
)

@app.get("/", response_class=HTMLResponse)
async def chat_interface(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/chat")
async def chat_api(request: Request, query: str = Form(...), history: str = Form("")):
    # Tìm kiếm tài liệu liên quan
    search_results = search_client.search(query)
    docs = [doc.get("content", "") for doc in search_results]
    docs_text = "\n".join(docs)

    messages = [
        {"role": "system", "content": "Bạn là một trợ lý AI thông minh."},
    ]

    if history:
        messages += json.loads(history)

    messages.append({
        "role": "user",
        "content": f"{query}\n\nTài liệu liên quan:\n{docs_text}"
    })

    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=0.7,
            max_tokens=800
        )
        raw_answer = response.choices[0].message.content.strip()
        answer = markdown2.markdown(raw_answer)
    except Exception as e:
        answer = f"Lỗi từ OpenAI API: {str(e)}"

    messages.append({"role": "assistant", "content": answer})

    return JSONResponse(content={"answer": answer, "history": messages})
