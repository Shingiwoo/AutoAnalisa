from app.v2_schemas.llm_output import LlmOutput


def validate_output(data: dict) -> LlmOutput:
    """Coerce & validate dict -> LlmOutput. Raise error if invalid."""
    return LlmOutput.model_validate(data)

