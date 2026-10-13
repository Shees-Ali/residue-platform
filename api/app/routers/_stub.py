from fastapi import HTTPException


def todo(story: str) -> None:
    raise HTTPException(status_code=501, detail=f"Not implemented ({story})")
