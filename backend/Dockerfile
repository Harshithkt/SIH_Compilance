FROM python:3.12-slim-bookworm

# Tesseract is the offline fallback reader; the Devanagari font is what keeps Hindi
# values legible in generated dockets.
RUN apt-get update && apt-get install -y --no-install-recommends \
  tesseract-ocr tesseract-ocr-hin fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The PaddleOCR offline engine is opt-in: paddlepaddle plus the PP-OCRv6 weights add
# several hundred megabytes, which is not worth carrying in a deployment that has
# Nebius configured and Tesseract as its offline floor.
#   docker build --build-arg INSTALL_PADDLE=1 ./backend
ARG INSTALL_PADDLE=0

COPY requirements.txt requirements-paddle.txt ./
RUN pip install --no-cache-dir -r requirements.txt pytesseract \
    && if [ "$INSTALL_PADDLE" = "1" ]; then \
         pip install --no-cache-dir -r requirements-paddle.txt; \
       fi

COPY app ./app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
