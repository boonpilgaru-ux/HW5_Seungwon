from typing import Literal

from pydantic import BaseModel, Field


class HumanReview(BaseModel):
    approved_by: str = Field(min_length=1, max_length=100)


class ResetConfirmation(BaseModel):
    confirmation: Literal["RESET"]
