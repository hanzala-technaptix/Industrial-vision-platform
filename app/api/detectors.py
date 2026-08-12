from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/detectors")
def get_detectors(request: Request):
    pipe = getattr(request.app.state, "pipeline", None)
    if pipe is None:
        return {"detectors": []}
    return {"detectors": pipe.get_detector_states()}
