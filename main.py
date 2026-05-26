from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import io
import os
from fishaudio import AsyncFishAudio
from fishaudio.types import ReferenceAudio
 
app = FastAPI()
 
FISH_API_KEY = os.environ.get("FISH_API_KEY", "")
 
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
        # Читаем все загруженные файлы как ReferenceAudio
        references = []
        for f in files:
            audio_bytes = await f.read()
            references.append(ReferenceAudio(audio=audio_bytes))
 
        async with AsyncFishAudio(api_key=FISH_API_KEY) as client:
            stream = await client.tts.stream(
                text=prompt,
                references=references,
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
 
