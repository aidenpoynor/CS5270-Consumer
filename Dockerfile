FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY consumer/ consumer/

RUN mkdir -p logs

ENTRYPOINT ["python", "-m", "consumer.main"]
CMD ["-s", "dynamodb", "-rq", "cs5270-requests"]
