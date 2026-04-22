FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY schema/ /app/schema/

# Ensure data directories are writeable by any UID (supports 'user: 1000:1000' in compose)
RUN chmod -R 777 /app/wiki /app/sources /app/snapshots /app/archive /app/schema

EXPOSE 8300

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8300"]
