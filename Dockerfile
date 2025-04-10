# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirement trước để cache install
COPY requirements.txt .

# Cài thư viện trước
RUN pip install --no-cache-dir -r requirements.txt

# Copy phần còn lại (code, html, css...)
COPY . .

CMD ["uvicorn", "app2:app", "--host", "0.0.0.0", "--port", "8000"]
