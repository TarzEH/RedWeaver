FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/knowledge_service ./src/knowledge_service

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
EXPOSE 8100

CMD ["uvicorn", "knowledge_service.main:app", "--host", "0.0.0.0", "--port", "8100"]
