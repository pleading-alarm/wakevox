from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import io
import os
import subprocess
import tempfile
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
 
def convert_to_wav(audio_bytes: bytes, input_ext: str = "m4a") -> bytes:
    with tempfile.NamedTemporaryFile(suffix=f".{input_ext}", delete=False) as inp:
        inp.write(audio_bytes)
        inp_path = inp.name
 
    out_path = inp_path.replace(f".{input_ext}", ".wav")
 
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", inp_path, "-ar", "44100", "-ac", "1", out_path],
            check=True,
            capture_output=True
        )
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(inp_path)
        if os.path.exists(out_path):
            os.unlink(out_path)
 
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
 
        # Файлы пользователя (до 2 штук)
        for f in files[:2]:
            raw = await f.read()
            filename = f.filename or "audio.m4a"
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "m4a"
            print(f"Received: {filename}, size: {len(raw)} bytes, ext: {ext}")
            wav = convert_to_wav(raw, ext)
            print(f"Converted to wav: {len(wav)} bytes")
            references.append(ReferenceAudio(audio=wav, text=""))
 
        # Emotion sample — от Android (3 раза)
        if emotion:
            for i, e in enumerate(emotion):
                emotion_raw = await e.read()
                if emotion_raw:
                    emotion_filename = e.filename or "emotion.ogg"
                    emotion_ext = emotion_filename.rsplit(".", 1)[-1].lower() if "." in emotion_filename else "ogg"
                    emotion_wav = convert_to_wav(emotion_raw, emotion_ext)
                    references.append(ReferenceAudio(audio=emotion_wav, text=""))
                    print(f"Emotion sample {i+1} added: {len(emotion_wav)} bytes")
        else:
            print("No emotion sample provided")
 
        session = Session(FISH_API_KEY)
 
        text_to_generate = prompt if prompt.strip() else GENERATE_TEXT
 
        audio_chunks = []
        for chunk in session.tts(TTSRequest(
            text=text_to_generate,
            references=references,
            format="mp3",
        )):
            audio_chunks.append(chunk)
 
        audio_bytes = b"".join(audio_chunks)
        print(f"Generated: {len(audio_bytes)} bytes")
 
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=generated.mp3"}
        )
 
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"FFmpeg error: {e.stderr.decode()}")
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
 
