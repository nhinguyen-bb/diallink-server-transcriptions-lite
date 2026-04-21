import os
import tempfile

import boto3

S3_BUCKET = os.getenv("S3_BUCKET", "diallink-transcription-audio")
S3_REGION = os.getenv("AWS_REGION", "us-east-1")

s3_client = boto3.client("s3", region_name=S3_REGION)


def upload_audio(s3_key: str, file_bytes: bytes):
    s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_bytes)


def download_audio(s3_key: str) -> str:
    suffix = os.path.splitext(s3_key)[-1] or ".wav"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    s3_client.download_fileobj(S3_BUCKET, s3_key, tmp)
    tmp.close()
    return tmp.name


def delete_audio(s3_key: str):
    s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)


def audio_exists(s3_key: str) -> bool:
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        return True
    except s3_client.exceptions.ClientError:
        return False
