import os
from pathlib import Path

from dopplersdk import DopplerSDK
from fastapi import Header, HTTPException

from .constants import DOPPLER_PROJECT_NAME
from .exceptions import InvalidAPIKey, UserException


def manage_audio_files(directory: str, max_files: int = 5):
    """
    Ensures the directory only keeps up to 'max_files' files.
    Deletes older files if needed.
    """

    files = sorted(
        Path(directory).iterdir(),
        key=lambda f: f.stat().st_mtime,  # Sort by modification time
        reverse=True,
    )
    for file in files[max_files:]:
        file.unlink()


def verify_api_key(x_api_key: str = Header(...)):
    try:
        if x_api_key != get_api_key():
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: Invalid API Key",
            )
    except Exception as e:
        raise UserException(f"Failed to get API key in Doppler: {str(e)}")


def get_api_key():
    """
    Fetches the value of api key from Doppler.
    :return: str: The computed value of the secret if found.
    """
    api_key = os.getenv("API_KEY")
    if api_key:
        return api_key

    doppler_token = os.getenv("DOPPLER_TOKEN")
    if not doppler_token:
        raise UserException("Doppler Token not found. Please configure the project correctly.")
    doppler_config = os.getenv("DOPPLER_CONFIG")
    if not doppler_config:
        raise UserException("Doppler config not found. Please configure the project correctly.")

    doppler = DopplerSDK()
    doppler.set_access_token(doppler_token)
    secret = doppler.secrets.get(project=DOPPLER_PROJECT_NAME, config=doppler_config, name="API_KEY")
    api_key = secret.value.get("computed")
    if not api_key:
        raise InvalidAPIKey()
    return api_key
