from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import io
import os
import uuid
import requests
from fish_audio_sdk import Session, TTSRequest, ReferenceAudio
 
app = FastAPI()
 
FISH_API_KEY = os.environ.get("FISH_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
 
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


@app.post("/generate_emotional")
async def generate_emotional(
    files: list[UploadFile] = File(...),
    emotional_audio: UploadFile = File(...),
):
    """
    ElevenLabs Voice Changer.

    Тембр (files, макс. 2 — те же референсы, что и для Fish Audio) клонируется
    ВРЕМЕННО прямо на время этого запроса, а не хранится постоянно: иначе при
    тысячах пользователей мы упрёмся в лимит voice slots тарифа ElevenLabs.

    Шаги: clone (Instant Voice Cloning) -> speech-to-speech (Voice Changer,
    перенос тайминга/эмоции с emotional_audio на этот тембр) -> delete клона.
    Удаление клона выполняется в finally, чтобы слот освобождался даже если
    speech-to-speech упал с ошибкой.
    """
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ElevenLabs API key not configured")

    if not files:
        raise HTTPException(status_code=400, detail="No reference audio files provided")

    voice_id = None
    try:
        # 1) Клонируем тембр (Instant Voice Cloning) — максимум 2 файла, как у Fish Audio
        clone_parts = []
        for f in files[:2]:
            raw = await f.read()
            filename = f.filename or "reference.m4a"
            print(f"Reference for cloning: {filename}, {len(raw)} bytes")
            clone_parts.append(("files[]", (filename, raw, "audio/mpeg")))

        temp_name = f"wakevox_temp_{uuid.uuid4().hex[:10]}"

        clone_resp = requests.post(
            f"{ELEVENLABS_BASE}/voices/add",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            data={"name": temp_name},
            files=clone_parts,
            timeout=60,
        )
        clone_resp.raise_for_status()
        voice_id = clone_resp.json()["voice_id"]
        print(f"Cloned temporary voice: {voice_id}")

        # 2) Voice Changer — переносим запись эмоционального исполнения на этот тембр
        emotional_raw = await emotional_audio.read()
        emotional_filename = emotional_audio.filename or "emotion.m4a"
        print(f"Emotional performance: {emotional_filename}, {len(emotional_raw)} bytes")

        sts_resp = requests.post(
            f"{ELEVENLABS_BASE}/speech-to-speech/{voice_id}",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            # eleven_multilingual_sts_v2 — иначе дефолт eleven_english_sts_v2
            # будет хуже работать с не-английскими записями (14 языков приложения)
            data={"model_id": "eleven_multilingual_sts_v2"},
            files={"audio": (emotional_filename, emotional_raw, "audio/mpeg")},
            timeout=120,
        )
        sts_resp.raise_for_status()
        audio_bytes = sts_resp.content
        print(f"Generated emotional voice: {len(audio_bytes)} bytes")

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=generated_emotional.mp3"}
        )

    except requests.HTTPError as e:
        detail = e.response.text if e.response is not None else str(e)
        print(f"ElevenLabs error: {detail}")
        raise HTTPException(status_code=500, detail=detail)
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 3) Удаляем временный клон в любом случае — иначе слот останется занят навсегда
        if voice_id:
            try:
                del_resp = requests.delete(
                    f"{ELEVENLABS_BASE}/voices/{voice_id}",
                    headers={"xi-api-key": ELEVENLABS_API_KEY},
                    timeout=30,
                )
                print(f"Deleted temp voice {voice_id}: status {del_resp.status_code}")
            except Exception as cleanup_err:
                print(f"WARNING: failed to delete temp voice {voice_id}: {cleanup_err}")
