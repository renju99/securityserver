FROM python:3.9-slim

WORKDIR /app

# Install system dependencies (including LibreOffice for conversion)
RUN apt-get update && apt-get install -y \
    libreoffice-writer-nogui \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
