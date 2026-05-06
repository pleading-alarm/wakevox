from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import requests
import io
import os

app = FastAPI()

FISH_API_KEY = os.environ.get("FISH_API_KEY", "")

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/generate")
async def generate(
    prompt: str = Form(...),
    files: list[UploadFile] = File(...)
):
    if not FISH_API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")

    headers = {"Authorization": f"Bearer {FISH_API_KEY}"}

    # Клонируем голос
    files_data = []
    for f in files:
        content = await f.read()
        files_data.append(("voices", (f.filename, content, "audio/mpeg")))

    clone_response = requests.post(
        "https://api.fish.audio/model",
        headers=headers,
        data={
            "visibility": "private",
            "title": "ex_voice",
            "train_mode": "fast"
        },
        files=files_data,
        timeout=120
    )

    if clone_response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Clone error: {clone_response.text}")

    voice_id = clone_response.json()["_id"]

    # Генерируем речь
    tts_response = requests.post(
        "https://api.fish.audio/v1/tts",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "text": prompt,
            "reference_id": voice_id,
            "format": "mp3"
        },
        timeout=120
    )

    # Удаляем голос
    requests.delete(
        f"https://api.fish.audio/model/{voice_id}",
        headers=headers,
        timeout=30
    )

    if tts_response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"TTS error: {tts_response.text}")

    return StreamingResponse(
        io.BytesIO(tts_response.content),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "attachment; filename=generated.mp3"}
    )
