"""Errors that cross the engine boundary. The API maps these to HTTP."""

from pydantic import BaseModel, ConfigDict, Field


class EngineError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


class EngineErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    http_status: int = 400
    details: dict = Field(default_factory=dict)
