from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import io
import os
import httpx
import base64
 
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
        ref_audio_b64 = base64.b64encode(ref_audio).decode("utf-8")
 
        payload = {
            "text": prompt,
            "format": "mp3",
            "references": [
                {
                    "audio": ref_audio_b64,
                    "text": ""
                }
            ]
        }
 
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                FISH_TTS_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {FISH_API_KEY}",
                    "Content-Type": "application/json",
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
