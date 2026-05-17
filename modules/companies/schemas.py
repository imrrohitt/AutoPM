from uuid import UUID

from pydantic import BaseModel, Field


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class CompanyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
