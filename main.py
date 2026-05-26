
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import io
import os
import httpx
import json
 
app = FastAPI()
 
FISH_API_KEY = os.environ.get("FISH_API_KEY", "")
FISH_TTS_URL = "https://api.fish.audio/v1/tts"
 
@app.get("/")
def root():
    return {"status": "ok"}
 
@app.post("/generate")
async def generate(
    prompt: str = Form(...),
    files: list[UploadFile] = File(...),
):
    if not FISH_API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")
 
    if not files:
        raise HTTPException(status_code=400, detail="No reference audio files provided")
 
    try:
        ref_audio = await files[0].read()
        filename = files[0].filename or "audio.m4a"
 
        # Fish Audio принимает multipart: request (JSON) + audio файл
        request_data = {
            "text": prompt,
            "format": "mp3",
            "references": [{"text": ""}]
        }
 
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                FISH_TTS_URL,
                headers={"Authorization": f"Bearer {FISH_API_KEY}"},
                files={
                    "request": (None, json.dumps(request_data), "application/json"),
                    "references[0].audio": (filename, ref_audio, "audio/mpeg"),
                }
            )
 
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Fish Audio error: {response.text}")
 
        return StreamingResponse(
            io.BytesIO(response.content),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=generated.mp3"}
        )
 
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
