from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import io
import os
import tempfile

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

    # Сохраняем файлы во временную папку
    temp_files = []
    try:
        for f in files:
            content = await f.read()
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".m4a")
            tmp.write(content)
            tmp.close()
            temp_files.append((f.filename, tmp.name))

        async with httpx.AsyncClient(timeout=120) as client:
            # Открываем файлы и отправляем
            open_files = []
            file_handles = []
            for filename, path in temp_files:
                fh = open(path, "rb")
                file_handles.append(fh)
                open_files.append(("voices", (filename, fh, "audio/mpeg")))

            clone_response = await client.post(
                "https://api.fish.audio/model",
                headers=headers,
                data={
                    "visibility": "private",
                    "title": "ex_voice",
                    "train_mode": "fast"
                },
                files=open_files
            )

            for fh in file_handles:
                fh.close()

            if clone_response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Clone error: {clone_response.text}")

            voice_id = clone_response.json()["_id"]

            tts_response = await client.post(
                "https://api.fish.audio/v1/tts",
                headers={**headers, "Content-Type": "application/json"},
                json={"text": prompt, "reference_id": voice_id, "format": "mp3"}
            )

            await client.delete(f"https://api.fish.audio/model/{voice_id}", headers=headers)

            if tts_response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"TTS error: {tts_response.text}")

            return StreamingResponse(
                io.BytesIO(tts_response.content),
                media_type="audio/mpeg",
                headers={"Content-Disposition": "attachment; filename=generated.mp3"}
            )
    finally:
        for _, path in temp_files:
            try:
                os.unlink(path)
            except:
                pass
