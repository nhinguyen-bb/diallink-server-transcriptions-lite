# DialLink Transcriptions Service

## Overview
The **DialLink Transcriptions Service** provides an API for transcribing audio files into text using the **WhisperX** model. API authentication is enforced via an API key to ensure secure access.

## Features
- Transcribes audio files (`.wav`, `.mp3`, `.flac`) to text.
- Supports optional parameters:
  - **Model** WhisperX model to use
  - **Custom prompts** to guide transcription.
  - **Response formats**: JSON, plain text, and verbose JSON.
  - **Temperature control** for randomness in output.
  - **Language detection and specification**.
- Authentication via an API key.

---

## API Endpoint

### Transcription
**Endpoint**: `/transcriptions/`  
**Method**: `POST`  
**Description**: Transcribes the uploaded audio file into text.

**Headers**:
- `x-api-key`: API key for authentication.

**Form Data**:

| **Field**         | **Required** | **Description**                                                     | **Default**      |
|--------------------|--------------|---------------------------------------------------------------------|------------------|
| `file`            | Yes          | Path to the audio file to transcribe (`.wav`, `.mp3`, `.flac`).     | -                |
| `model`           | No           | WhisperX model to use.                                              | `base`           |
| `prompt`          | No           | Text prompt to guide the transcription.                             | `""` (empty)     |
| `response_format` | No           | Output format: `json`, `text`, or `verbose_json`.                   | `json`           |
| `temperature`     | No           | Controls randomness in transcription (range: 0.0 to 1.0).           | `0.0`            |
| `language`        | No           | Language of the audio file (e.g., `en` for English).                | `en`             |

**Example Request** (using `curl`):
```
curl -X POST "http://<host>:<port>/transcriptions/" \
    -H "Content-Type: multipart/form-data" \
    -H "x-api-key: <YOUR_API_KEY>" \
    -F "file=@/path/to/audio/file.mp3" \
    -F "response_format=json" \
    -F "language=en"
```

---

## Response Formats

1. **JSON (Default)**: Returns a JSON object with the transcribed text.
   ```
   {
     "text": "This is the transcribed text of the audio file."
   }
   ```

2. **Plain Text**: Returns only the transcribed text as plain text.
   ```
   This is the transcribed text of the audio file.
   ```

3. **Verbose JSON**: Returns detailed metadata, including transcription segments.
   ```
   {
     "text": "This is the transcribed text of the audio file.",
     "segments": [
       {
         "id": 0,
         "start": 0.0,
         "end": 5.0,
         "text": "This is the transcribed text."
       },
       {
         "id": 1,
         "start": 5.0,
         "end": 10.0,
         "text": "This is another segment of the transcription."
       }
     ],
     "language": "en"
   }
   ```

To specify a format, include the `response_format` field in the request (`json`, `text`, or `verbose_json`).

---

## Authentication
API requests must include the `x-api-key` header with a valid API key to access the service.

**Example**:
```
-H "x-api-key: <YOUR_API_KEY>"
```

---

## Requirements
- Python 3.9+
- FastAPI
- WhisperX Model
- Dependencies listed in `requirements.txt`.

## Environment Variables
- `ASR_DEVICE`: Device for model execution (default: `cpu`)
- `ASR_COMPUTE_TYPE`: Compute precision (default: `int8`, use `int16` for CPU)
- `WHISPER_MODEL`: Model size to use (default: `base`)

---

## Deployment
1. Clone the repository.
2. Install dependencies:
   ```
   make setup
   ```
3. Run the service:
   ```
   # Using environment variables for local testing
   ASR_DEVICE=cpu ASR_COMPUTE_TYPE=int16 uvicorn app:app --host 0.0.0.0 --port 9001
   
   # Or using the Makefile
   make start
   ```

## Health Check
The service provides a health check endpoint at `/healthz`:
```
curl http://localhost:9001/healthz
```
