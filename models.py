from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class AgentCommand(BaseModel):
    command: Literal["navigate", "back", "click", "type", "select", "finish", "wait_for_user"]
    url: Optional[str] = None
    selector: Optional[str] = None
    description: Optional[str] = None
    text: Optional[str] = None
    value: Optional[str] = None
    status: Optional[Literal["success", "failed"]] = None
    message: Optional[str] = None

class ScrapedElement(BaseModel):
    text: str
    selector: str
    type: str
    attributes: Dict[str, str] = {}

class ScrapedPageInfo(BaseModel):
    url: str
    title: str
    links: List[ScrapedElement]
    buttons: List[ScrapedElement]
    inputs: List[ScrapedElement]
    texts: List[str]

class StartingUrlResponse(BaseModel):
    url: str
