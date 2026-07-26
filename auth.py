import os
from fastapi import Header, HTTPException, status
 
APP_API_KEY = os.environ.get("WAKEVOX_API_KEY", "")
 
 
async def verify_app_key(x_wakevox_key: str | None = Header(default=None)):
    """
    Dependency для FastAPI-роутов: проверяет заголовок X-WakeVox-Key.
    Использование: @app.post("/generate", dependencies=[Depends(verify_app_key)])
    """
    if not APP_API_KEY:
        # Ключ не настроен на сервере — не блокируем, но громко пишем в лог,
        # чтобы это не осталось незамеченным.
        print("WARNING: WAKEVOX_API_KEY is not set on the server!")
        return
 
    if x_wakevox_key is None or x_wakevox_key != APP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
