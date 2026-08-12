from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/cameras")
def list_cameras(request: Request):
    cams = getattr(request.app.state, "camera_manager", None)
    return {"cameras": cams.list_cameras() if cams is not None else []}
