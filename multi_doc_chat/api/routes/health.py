from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from multi_doc_chat.utils.checkpointer import CheckpointerManager
from multi_doc_chat.api.schemas import HealthDb


router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/db", response_model=HealthDb)
async def health_db():
    try:
        cm = CheckpointerManager()
        checkpointer = await cm.get_checkpointer()
        # Try open/close context to verify connectivity
        async with checkpointer:  # type: ignore
            pass
        return HealthDb(ok=True)
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=HealthDb(ok=False, error=str(e)).model_dump())


