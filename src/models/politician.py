from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Party(str, Enum):
    D = "D"
    R = "R"
    I = "I"


class Chamber(str, Enum):
    House = "House"
    Senate = "Senate"


class Politician(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: Optional[int] = None
    name: str
    party: Party
    chamber: Chamber
