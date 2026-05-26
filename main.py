from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import io
import os
import subprocess
import tempfile
from fish_audio_sdk import Session, TTSRequest, ReferenceAudio
 
app = FastAPI()
 
FISH_API_KEY = os.environ.get("FISH_API_KEY", "")
 
@app.get("/")
def root():
    return {"status": "ok"}
 
def convert_to_wav(audio_bytes: bytes, input_ext: str = "m4a") -> bytes:
    """Convert any audio format to wav using ffmpeg."""
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
):
    if not FISH_API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")
 
    if not files:
        raise HTTPException(status_code=400, detail="No reference audio files provided")
 
    try:
        ref_audio_raw = await files[0].read()
        filename = files[0].filename or "audio.m4a"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "m4a"
 
        print(f"Received: {filename}, size: {len(ref_audio_raw)} bytes, ext: {ext}")
 
        # Конвертируем в wav
        ref_audio = convert_to_wav(ref_audio_raw, ext)
        print(f"Converted to wav: {len(ref_audio)} bytes")
 
        session = Session(FISH_API_KEY)
 
        audio_chunks = []
        for chunk in session.tts(TTSRequest(
            text=prompt,
            references=[ReferenceAudio(audio=ref_audio, text="")],
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
 
