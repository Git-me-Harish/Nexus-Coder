"""
Shared camelCase serialization — the frontend (src/lib/nexus/client.ts and
every component consuming it) expects camelCase JSON exactly as Prisma
produced it (tokensUsed, currentPhase, baseModelId, ...). Rather than touch
every frontend call site, every response schema aliases its snake_case
Python fields to camelCase on the wire via this shared config.
"""
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )
