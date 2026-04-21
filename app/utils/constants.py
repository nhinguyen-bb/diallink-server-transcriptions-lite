import os

import torch

DEFAULT_MODEL_TYPE = os.getenv("WHISPER_MODEL", "medium")

ASR_DEVICE = os.getenv("ASR_DEVICE")
if not ASR_DEVICE:
    ASR_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

ASR_COMPUTE_TYPE = os.getenv("ASR_COMPUTE_TYPE")
if not ASR_COMPUTE_TYPE:
    ASR_COMPUTE_TYPE = "float16" if ASR_DEVICE == "cuda" else "int8"

current_dir = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = f"{current_dir}/../audios"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DOPPLER_PROJECT_NAME = "diallink-server-transcriptions"

