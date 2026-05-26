from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import io
import os
from fish_audio_sdk import Session, TTSRequest, ReferenceAudio
 
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
        ref_audio = await files[0].read()
 
        session = Session(FISH_API_KEY)
 
        audio_chunks = []
        for chunk in session.tts(TTSRequest(
            text=prompt,
            references=[ReferenceAudio(audio=ref_audio, text="")],
            format="mp3",
        )):
            audio_chunks.append(chunk)
 
        audio_bytes = b"".join(audio_chunks)
 
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=generated.mp3"}
        )
 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
