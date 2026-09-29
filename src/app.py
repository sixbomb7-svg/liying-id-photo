# AGPL-3.0-or-later: derived service integration for LiYing.
import base64
import io
import os
import tempfile
import threading
from pathlib import Path

import cv2 as cv
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from tool.ImageProcessor import ImageProcessor

APP_NAME = 'LiYing ID Photo API'
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_OUTPUT_EDGE = int(os.getenv('LIYING_MAX_OUTPUT_EDGE', '1600'))
MODEL_DIR = Path(os.getenv('LIYING_MODEL_DIR', '/app/models')).resolve()
MODEL_PATHS = {
    'yolo': MODEL_DIR / 'yolov8n-pose.onnx',
    'yunet': MODEL_DIR / 'face_detection_yunet_2023mar.onnx',
    'rmbg': MODEL_DIR / 'RMBG-1.4-model.onnx',
}
INFERENCE_LOCK = threading.Lock()

app = FastAPI(title=APP_NAME, version='1.0.0')


def validate_models():
    missing = [str(path) for path in MODEL_PATHS.values() if not path.is_file()]
    if missing:
        raise RuntimeError('LiYing model files are missing: ' + ', '.join(missing))


def parse_background(value: str) -> list[int]:
    text = str(value or 'transparent').strip().lower()
    if text == 'transparent':
        return [255, 255, 255, 0]
    if text.startswith('#') and len(text) == 7:
        try:
            return [int(text[index:index + 2], 16) for index in (1, 3, 5)]
        except ValueError:
            pass
    raise HTTPException(status_code=422, detail='background must be transparent or #RRGGBB')


def validate_image(data: bytes) -> None:
    if not data:
        raise HTTPException(status_code=400, detail='image is required')
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail='image exceeds the 10 MiB limit')
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise HTTPException(status_code=415, detail='image must be a valid JPEG or PNG') from error


def process_image(image_bytes: bytes, suffix: str, background: list[int]) -> bytes:
    with tempfile.TemporaryDirectory(prefix='liying-') as directory:
        source_path = Path(directory) / ('source' + suffix)
        source_path.write_bytes(image_bytes)
        with INFERENCE_LOCK:
            processor = ImageProcessor(
                str(source_path),
                yolov8_model_path=str(MODEL_PATHS['yolo']),
                yunet_model_path=str(MODEL_PATHS['yunet']),
                RMBG_model_path=str(MODEL_PATHS['rmbg']),
                rgb_list=background,
            )
            processor.change_background(background)
            output = processor.photo.image
        if output is None:
            raise RuntimeError('LiYing did not produce an image')
        height, width = output.shape[:2]
        edge = max(height, width)
        if edge > MAX_OUTPUT_EDGE:
            scale = MAX_OUTPUT_EDGE / edge
            output = cv.resize(output, (round(width * scale), round(height * scale)), interpolation=cv.INTER_AREA)
        if output.ndim == 3 and output.shape[2] == 4:
            rgba = cv.cvtColor(output, cv.COLOR_BGRA2RGBA)
            image = Image.fromarray(rgba, 'RGBA')
        else:
            rgb = cv.cvtColor(output, cv.COLOR_BGR2RGB)
            image = Image.fromarray(rgb, 'RGB')
        buffer = io.BytesIO()
        image.save(buffer, format='PNG', optimize=True)
        return buffer.getvalue()


@app.on_event('startup')
def startup() -> None:
    validate_models()


@app.get('/healthz')
def healthz() -> dict:
    return {'ok': True, 'service': APP_NAME, 'models': {name: path.name for name, path in MODEL_PATHS.items()}}


@app.post('/v1/id-photo/segment')
async def segment(
    image: UploadFile = File(...),
    width: int = Form(...),
    height: int = Form(...),
    background: str = Form('transparent'),
) -> dict:
    if not 1 <= width <= 4096 or not 1 <= height <= 4096:
        raise HTTPException(status_code=422, detail='width and height must be between 1 and 4096')
    image_bytes = await image.read(MAX_UPLOAD_BYTES + 1)
    validate_image(image_bytes)
    rgb_or_rgba = parse_background(background)
    suffix = Path(image.filename or 'upload.jpg').suffix.lower()
    if suffix not in {'.jpg', '.jpeg', '.png'}:
        suffix = '.png'
    try:
        png = process_image(image_bytes, suffix, rgb_or_rgba)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=422, detail='LiYing processing failed: ' + str(error)) from error
    return {
        'imageBase64': base64.b64encode(png).decode('ascii'),
        'mimeType': 'image/png',
        'width': width,
        'height': height,
    }

