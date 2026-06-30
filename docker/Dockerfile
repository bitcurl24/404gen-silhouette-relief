FROM python:3.12.8-slim-bookworm

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY miner_service.py generator.py /app/

EXPOSE 10006
CMD ["uvicorn", "miner_service:app", "--host", "0.0.0.0", "--port", "10006"]
