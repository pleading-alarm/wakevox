from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import httpx
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

    async with httpx.AsyncClient(timeout=120) as client:
        form_data = {"visibility": "private", "voice_name": "ex_voice"}
        files_data = []
        for f in files:
            content = await f.read()
            files_data.append(("voices", (f.filename, content, f.content_type)))

        clone_response = await client.post(
            "https://api.fish.audio/model",
            headers={"Authorization": f"Bearer {FISH_API_KEY}"},
            data=form_data,
            files=files_data
        )

        if clone_response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Clone error: {clone_response.text}")

        voice_id = clone_response.json()["_id"]

        tts_response = await client.post(
            "https://api.fish.audio/v1/tts",
            headers={
                "Authorization": f"Bearer {FISH_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "text": prompt,
                "reference_id": voice_id,
                "format": "mp3"
            }
        )

        if tts_response.status_code != 200:
            await client.delete(
                f"https://api.fish.audio/model/{voice_id}",
                headers={"Authorization": f"Bearer {FISH_API_KEY}"}
            )
            raise HTTPException(status_code=400, detail=f"TTS error: {tts_response.text}")

        audio_bytes = tts_response.content

        await client.delete(
            f"https://api.fish.audio/model/{voice_id}",
            headers={"Authorization": f"Bearer {FISH_API_KEY}"}
        )

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=generated.mp3"}
        )
