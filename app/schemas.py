from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field


class Interaction(BaseModel):
    trigger: Literal["onClick", "onHover", "onSwipe", "onFocus"] = "onClick"
    action: Literal["navigate", "toggle", "overlay", "scroll", "animate"] = "navigate"
    target: str  # Screen name or component ID
    transition: Optional[str] = "slide_left"  # slide_left, fade, push, etc.
    duration: Optional[int] = 300  # milliseconds

class ComponentState(BaseModel):
    name: str  # default, hover, pressed, selected, disabled
    properties: Dict[str, Any] = Field(default_factory=dict)  # styling changes

class Navigation(BaseModel):
    from_screen: str
    to_screen: str
    trigger_component: str  # button, card, chip that triggers navigation
    interaction: Interaction

class UIScreen(BaseModel):
    name: str
    layout: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured layout description returned by the LLM",
    )
    description: str
    interactions: List[Interaction] = Field(default_factory=list)
    component_states: List[ComponentState] = Field(default_factory=list)


class UIStyles(BaseModel):
    colors: Dict[str, str] = Field(default_factory=dict)
    typography: Dict[str, Any] = Field(default_factory=dict)
    components: List[str] = Field(default_factory=list)


class UIReport(BaseModel):
    project_name: str
    screens: List[UIScreen]
    styles: UIStyles
    summary: str
    navigation_flow: List[Navigation] = Field(default_factory=list)
    prototype_settings: Dict[str, Any] = Field(default_factory=dict)


class UIReportResponse(BaseModel):
    figma_url: Optional[str] = None
    report: UIReport
    prompt_used: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    llm_provider: str
    has_figma_access: bool
    sample_document_loaded: Optional[bool] = None
