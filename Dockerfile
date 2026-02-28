FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend/out ./frontend/out

EXPOSE 12222

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12222"]
