FROM python:3.11-slim

WORKDIR /app
ENV DATABASE_PROVIDER=postgresql
ENV DATABASE_URL=postgresql://postgres:postgres@localhost:5432/loanlens
ENV DIRECT_URL=postgresql://postgres:postgres@localhost:5432/loanlens
ENV PRISMA_SCHEMA_PATH=./schema.prisma

# Install system dependencies required for PyMuPDF and OCR providers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generate Prisma Client
RUN prisma generate --schema ./schema.prisma

EXPOSE 8000

CMD ["sh", "-c", "./scripts/migrate.sh && uvicorn main:app --host 0.0.0.0 --port 8000"]
