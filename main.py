from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import io
import os
from fish_audio_sdk import Session, TTSRequest, ReferenceAudio
 
app = FastAPI()
 
FISH_API_KEY = os.environ.get("FISH_API_KEY", "")
 
GENERATE_TEXT = (
    "[crying] Please... [sobbing] wake up... [weeping] I beg you... "
    "[moaning] I'm so sorry... [exhale] I was wrong... [crying] I love you so much... "
    "[sobbing] Please... [whispering] don't leave me... [crying] wake up..."
)
 
@app.get("/")
def root():
    return {"status": "ok"}
 
@app.post("/generate")
async def generate(
    prompt: str = Form(...),
    files: list[UploadFile] = File(...),
    emotion: list[UploadFile] = File(None),
):
    if not FISH_API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")
 
    if not files:
        raise HTTPException(status_code=400, detail="No reference audio files provided")
 
    try:
        references = []
 
        for f in files[:2]:
            raw = await f.read()
            filename = f.filename or "audio.m4a"
            print(f"Received: {filename}, size: {len(raw)} bytes")
            references.append(ReferenceAudio(audio=raw, text=""))
 
        if emotion:
            for i, e in enumerate(emotion):
                emotion_raw = await e.read()
                if emotion_raw:
                    print(f"Emotion sample {i+1}: {len(emotion_raw)} bytes")
                    references.append(ReferenceAudio(audio=emotion_raw, text=""))
        else:
            print("No emotion sample provided")
 
        session = Session(FISH_API_KEY)
        text_to_generate = prompt if prompt.strip() else GENERATE_TEXT
 
        audio_chunks = []
        for chunk in session.tts(TTSRequest(
            text=text_to_generate,
            references=references,
            format="mp3",
        ), backend="s2-pro"):
            audio_chunks.append(chunk)
 
        audio_bytes = b"".join(audio_chunks)
        print(f"Generated: {len(audio_bytes)} bytes")
 
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=generated.mp3"}
        )
 
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
