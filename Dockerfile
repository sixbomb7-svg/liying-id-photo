FROM python:3.11-slim

ARG LIYING_MODEL_URL=https://github.com/aoguai/LiYing/releases/download/v3.2.0/LiYing_model.zip
ARG LIYING_MODEL_SHA256=3f6d492ae664c346852366a29149d91cf3ce367ead9c32ee333101cccffefac9

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Models are fetched during image construction so the Git repository stays below GitHub's file-size limit.
RUN mkdir -p /app/models /tmp/liying-model \
    && curl --fail --location --retry 3 --output /tmp/liying-model.zip "$LIYING_MODEL_URL" \
    && echo "$LIYING_MODEL_SHA256  /tmp/liying-model.zip" | sha256sum -c - \
    && unzip -q /tmp/liying-model.zip -d /tmp/liying-model \
    && find /tmp/liying-model -type f \( -name 'face_detection_yunet_2023mar.onnx' -o -name 'RMBG-1.4-model.onnx' -o -name 'yolov8n-pose.onnx' \) -exec cp {} /app/models/ \; \
    && test -s /app/models/face_detection_yunet_2023mar.onnx \
    && test -s /app/models/RMBG-1.4-model.onnx \
    && test -s /app/models/yolov8n-pose.onnx \
    && rm -rf /tmp/liying-model /tmp/liying-model.zip

COPY src /app/src
COPY data /app/data

ENV PYTHONPATH=/app/src
ENV LIYING_MODEL_DIR=/app/models
ENV PORT=80
EXPOSE 80
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-80}"]

