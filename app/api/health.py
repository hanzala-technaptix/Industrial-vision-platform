from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request):
    state = request.app.state
    pipe = getattr(state, "pipeline", None)
    cams = getattr(state, "camera_manager", None)
    return {
        "status": "healthy" if pipe is not None else "starting",
        "pipeline": pipe.stats() if pipe is not None else None,
        "cameras": cams.list_cameras() if cams is not None else [],
    }
