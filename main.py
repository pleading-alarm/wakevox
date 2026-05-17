from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import io
import os
from fishaudio import AsyncFishAudio
from fishaudio.types import ReferenceAudio
 
app = FastAPI()
 
FISH_API_KEY = os.environ.get("FISH_API_KEY", "")
 
# ID модели голоса созданной на Fish Audio
VOICE_MODEL_ID = "592087783c2f4e19ac2683c3bb06735b"
 
# Текст с эмоциональными тегами Fish Audio S2
EMOTIONAL_TEXT = "(sobbing) Пожалуйста... вернись ко мне... (crying loudly) я не могу без тебя... (sighing) я так скучаю по тебе... прости меня..."
 
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
 
    try:
        async with AsyncFishAudio(api_key=FISH_API_KEY) as client:
            # Используем reference_id модели + эмоциональные теги
            stream = await client.tts.stream(
                text=EMOTIONAL_TEXT,
                reference_id=VOICE_MODEL_ID,
                format="mp3",
            )
            audio_bytes = await stream.collect()
 
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=generated.mp3"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
