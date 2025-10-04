from app.v2_schemas.market import MarketSnapshot
from app.v2_schemas.llm_output import LlmOutput
from app.v2_payloads.build import build
from app.services_v2.llm_client import LlmClient
from app.services_v2.validators import validate_output


async def analyze(snapshot: MarketSnapshot) -> LlmOutput:
    prompt = build(snapshot)
    client = LlmClient()
    raw = await client.structured_response(
        system=prompt.system, user=prompt.user, json_schema=prompt.json_schema
    )
    llm_obj = validate_output(raw)
    return llm_obj

