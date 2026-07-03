from pydantic import BaseModel


class ArtifactListResponse(BaseModel):
    files: list[str]
