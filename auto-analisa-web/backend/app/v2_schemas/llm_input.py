from pydantic import BaseModel
from typing import Any, Dict


class LlmPrompt(BaseModel):
    system: str
    user: str
    json_schema: Dict[str, Any]

