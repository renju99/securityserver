FROM python:3.9-slim

WORKDIR /app

RUN pip install fastapi uvicorn httpx python-multipart

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
