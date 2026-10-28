"""Real-ESRGAN inference and deterministic image tools."""
import io
import os
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageOps, UnidentifiedImageError
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
from app.resource_lock import ResourceLock
_lock = ResourceLock(ROOT/'.runtime/model-resources.lock')
_engine = None
_device = None
FILTERS = ('none', 'denoise', 'sharpen', 'blur', 'grayscale', 'sketch', 'edges')


def decode(raw):
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > int(os.getenv('MAX_INPUT_PIXELS', '12000000')):
                raise ValueError('Imagen excede el límite de píxeles')
            image = ImageOps.exif_transpose(source).convert('RGB')
            return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Imagen no válida') from exc


def model_path():
    path = Path(os.getenv('MODEL_PATH', 'weights/RealESRGAN_x4plus.pth'))
    return path if path.is_absolute() else ROOT / path


def get_engine():
    global _engine, _device
    with _lock:
        if _engine is None:
            from basicsr.archs.rrdbnet_arch import RRDBNet
            from realesrgan import RealESRGANer
            path = model_path()
            if not path.is_file():
                raise RuntimeError('Faltan los pesos RealESRGAN_x4plus.pth')
            _device = 'cuda' if torch.cuda.is_available() else 'cpu'
            net = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
            _engine = RealESRGANer(scale=4, model_path=str(path), model=net,
                                  tile=int(os.getenv('MODEL_TILE', '128')), tile_pad=10,
                                  pre_pad=0, half=_device == 'cuda', gpu_id=0 if _device == 'cuda' else None)
        return _engine, _device


def encode(image):
    ok, encoded = cv2.imencode('.png', image)
    if not ok:
        raise RuntimeError('Error codificando PNG')
    return encoded.tobytes()


def restore(raw, scale=4):
    image = decode(raw)
    # RRDBNet always computes x4 internally, even when requesting a smaller output.
    if image.shape[0] * image.shape[1] * 16 > int(os.getenv('MAX_INFERENCE_PIXELS', '48000000')):
        raise ValueError('Imagen demasiado grande para inferencia; reduzca a 3 MP o menos')
    with _lock, torch.inference_mode():
        engine, device = get_engine()
        output, _ = engine.enhance(image, outscale=scale)
    return encode(output), device, (image.shape[1], image.shape[0]), (output.shape[1], output.shape[0])


def edit(raw, brightness=0, contrast=1, filter_name='none'):
    if filter_name not in FILTERS:
        raise ValueError('Filtro inválido')
    image = decode(raw)
    image = np.clip(image.astype(np.float32) * float(contrast) + int(brightness), 0, 255).astype(np.uint8)
    if filter_name == 'denoise':
        image = cv2.fastNlMeansDenoisingColored(image, None, 5, 5, 7, 21)
    elif filter_name == 'sharpen':
        image = cv2.filter2D(image, -1, np.array([[0,-1,0],[-1,5,-1],[0,-1,0]]))
    elif filter_name == 'blur':
        image = cv2.GaussianBlur(image, (5,5), 0)
    elif filter_name == 'grayscale':
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif filter_name == 'edges':
        image = cv2.Canny(image, 80, 160)
    elif filter_name == 'sketch':
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image = cv2.divide(gray, 255 - cv2.GaussianBlur(255 - gray, (21,21), 0), scale=256)
    return encode(image)


def unload_engine():
    """Release superresolution weights before local diffusion (caller holds GPU lock)."""
    global _engine, _device
    with _lock:
        _engine = None
        _device = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
