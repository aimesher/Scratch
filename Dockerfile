# Reel Studio online: dashboard + Claude connector. Your data lives in /data (attach a volume there).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY igflow ./igflow
COPY config.example.yaml .
ENV REELSTUDIO_CONFIG=/data/config.yaml PYTHONUNBUFFERED=1
CMD ["python", "-m", "igflow", "serve"]
