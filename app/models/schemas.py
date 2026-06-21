from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ComponentType(str, Enum):
    BUTTON = "button"
    TEXT_INPUT = "text_input"
    TEXT_AREA = "text_area"
    LABEL = "label"
    IMAGE = "image"
    RECTANGLE = "rectangle"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    DROPDOWN = "dropdown"
    LINK = "link"
    TABLE = "table"
    DYNAMIC_PANEL = "dynamic_panel"
    REPEATER = "repeater"
    UNKNOWN = "unknown"


class InteractionEvent(str, Enum):
    ON_CLICK = "onClick"
    ON_MOUSE_ENTER = "onMouseEnter"
    ON_MOUSE_LEAVE = "onMouseLeave"
    ON_CHANGE = "onChange"
    ON_FOCUS = "onFocus"
    ON_BLUR = "onBlur"


class GenerateFormat(str, Enum):
    HTML_ONLY = "html_only"
    HTML_CSS = "html_css"
    FULL_PAGE = "full_page"


def _to_float(v: Any) -> Any:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _to_str(v: Any) -> Any:
    if v is None:
        return None
    return str(v)


class LenientModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        coerce_numbers_to_str=True,
        str_strip_whitespace=True,
    )


class Position(LenientModel):
    x: float = Field(0, description="组件左上角X坐标")
    y: float = Field(0, description="组件左上角Y坐标")

    @field_validator("x", "y", mode="before")
    @classmethod
    def _coerce_float(cls, v):
        return _to_float(v) if v is not None else 0.0


class Size(LenientModel):
    width: float = Field(0, description="组件宽度")
    height: float = Field(0, description="组件高度")

    @field_validator("width", "height", mode="before")
    @classmethod
    def _coerce_float(cls, v):
        return _to_float(v) if v is not None else 0.0


class BorderStyle(LenientModel):
    width: Optional[float] = None
    style: Optional[str] = None
    color: Optional[str] = None
    radius: Optional[float] = None

    @field_validator("width", "radius", mode="before")
    @classmethod
    def _coerce_float_opt(cls, v):
        return _to_float(v)

    @field_validator("style", "color", mode="before")
    @classmethod
    def _coerce_str_opt(cls, v):
        return _to_str(v)


class TextStyle(LenientModel):
    font_family: Optional[str] = None
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    color: Optional[str] = None
    text_align: Optional[str] = None
    line_height: Optional[float] = None

    @field_validator("font_size", "line_height", mode="before")
    @classmethod
    def _coerce_float_opt(cls, v):
        return _to_float(v)

    @field_validator("font_family", "font_weight", "color", "text_align", mode="before")
    @classmethod
    def _coerce_str_opt(cls, v):
        return _to_str(v)


class ComponentStyle(LenientModel):
    background_color: Optional[str] = None
    opacity: Optional[float] = None
    border: Optional[BorderStyle] = None
    text_style: Optional[TextStyle] = None
    padding: Optional[Dict[str, Any]] = None
    shadow: Optional[bool] = None

    @field_validator("opacity", mode="before")
    @classmethod
    def _coerce_float_opt(cls, v):
        return _to_float(v)

    @field_validator("background_color", mode="before")
    @classmethod
    def _coerce_str_opt(cls, v):
        return _to_str(v)

    @field_validator("shadow", mode="before")
    @classmethod
    def _coerce_bool(cls, v):
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            return v.lower() in ["true", "1", "yes", "y", "on"]
        return None

    @field_validator("padding", mode="before")
    @classmethod
    def _coerce_padding(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            return {str(k): float(val) if isinstance(val, (int, float)) else val for k, val in v.items()}
        return None


class Interaction(LenientModel):
    event: InteractionEvent = Field(InteractionEvent.ON_CLICK)
    action: str = Field("", description="触发动作描述，如跳转、显示隐藏等")
    target: Optional[str] = None

    @field_validator("event", mode="before")
    @classmethod
    def _coerce_event(cls, v):
        if v is None:
            return InteractionEvent.ON_CLICK
        if isinstance(v, InteractionEvent):
            return v
        s = str(v).strip()
        mapping = {
            "click": InteractionEvent.ON_CLICK,
            "onclick": InteractionEvent.ON_CLICK,
            "on_click": InteractionEvent.ON_CLICK,
            "mouseenter": InteractionEvent.ON_MOUSE_ENTER,
            "onmouseenter": InteractionEvent.ON_MOUSE_ENTER,
            "mouseover": InteractionEvent.ON_MOUSE_ENTER,
            "mouseleave": InteractionEvent.ON_MOUSE_LEAVE,
            "onmouseleave": InteractionEvent.ON_MOUSE_LEAVE,
            "mouseout": InteractionEvent.ON_MOUSE_LEAVE,
            "change": InteractionEvent.ON_CHANGE,
            "onchange": InteractionEvent.ON_CHANGE,
            "focus": InteractionEvent.ON_FOCUS,
            "onfocus": InteractionEvent.ON_FOCUS,
            "blur": InteractionEvent.ON_BLUR,
            "onblur": InteractionEvent.ON_BLUR,
        }
        normalized = s.lower().replace("-", "_").replace(" ", "")
        if normalized in mapping:
            return mapping[normalized]
        try:
            return InteractionEvent(s)
        except ValueError:
            return InteractionEvent.ON_CLICK

    @field_validator("action", mode="before")
    @classmethod
    def _coerce_action(cls, v):
        return str(v) if v is not None else ""

    @field_validator("target", mode="before")
    @classmethod
    def _coerce_str_opt(cls, v):
        return _to_str(v)


class AxureComponent(LenientModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        coerce_numbers_to_str=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
    )

    id: str = Field(..., description="组件唯一标识")
    name: Optional[str] = Field(None, description="组件名称")
    component_type: ComponentType = Field(ComponentType.UNKNOWN, description="组件类型")
    position: Position = Field(default_factory=Position)
    size: Size = Field(default_factory=Size)
    style: Optional[ComponentStyle] = None
    text: Optional[str] = Field(None, description="组件显示的文本内容")
    placeholder: Optional[str] = Field(None, description="占位符文本")
    default_value: Optional[str] = Field(None, description="默认值")
    interactions: List[Interaction] = Field(default_factory=list, description="交互事件列表")
    children: List["AxureComponent"] = Field(default_factory=list, description="子组件")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="原始数据备用")

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v):
        return str(v) if v is not None else ""

    @field_validator("name", "text", "placeholder", "default_value", mode="before")
    @classmethod
    def _coerce_str_opt(cls, v):
        return _to_str(v)

    @field_validator("component_type", mode="before")
    @classmethod
    def _coerce_component_type(cls, v):
        if v is None:
            return ComponentType.UNKNOWN
        if isinstance(v, ComponentType):
            return v
        s = str(v).strip().lower()
        mapping = {
            "button": ComponentType.BUTTON,
            "btn": ComponentType.BUTTON,
            "input": ComponentType.TEXT_INPUT,
            "textinput": ComponentType.TEXT_INPUT,
            "text_input": ComponentType.TEXT_INPUT,
            "textbox": ComponentType.TEXT_INPUT,
            "textarea": ComponentType.TEXT_AREA,
            "text_area": ComponentType.TEXT_AREA,
            "label": ComponentType.LABEL,
            "text": ComponentType.LABEL,
            "image": ComponentType.IMAGE,
            "img": ComponentType.IMAGE,
            "rect": ComponentType.RECTANGLE,
            "rectangle": ComponentType.RECTANGLE,
            "box": ComponentType.RECTANGLE,
            "checkbox": ComponentType.CHECKBOX,
            "check": ComponentType.CHECKBOX,
            "radio": ComponentType.RADIO,
            "radiobutton": ComponentType.RADIO,
            "dropdown": ComponentType.DROPDOWN,
            "select": ComponentType.DROPDOWN,
            "combobox": ComponentType.DROPDOWN,
            "link": ComponentType.LINK,
            "hyperlink": ComponentType.LINK,
            "anchor": ComponentType.LINK,
            "table": ComponentType.TABLE,
            "grid": ComponentType.TABLE,
            "panel": ComponentType.DYNAMIC_PANEL,
            "dynamic_panel": ComponentType.DYNAMIC_PANEL,
            "dynamicpanel": ComponentType.DYNAMIC_PANEL,
            "repeater": ComponentType.REPEATER,
        }
        normalized = s.replace("-", "_").replace(" ", "")
        if normalized in mapping:
            return mapping[normalized]
        try:
            return ComponentType(s)
        except ValueError:
            return ComponentType.UNKNOWN

    @field_validator("interactions", mode="before")
    @classmethod
    def _coerce_interactions(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, Interaction):
                    result.append(item)
                elif isinstance(item, dict):
                    try:
                        result.append(Interaction.model_validate(item))
                    except Exception:
                        try:
                            if "event" not in item and "action" in item:
                                result.append(Interaction.model_validate({"event": "onClick", "action": str(item["action"])}))
                        except Exception:
                            pass
                elif isinstance(item, str):
                    try:
                        result.append(Interaction.model_validate({"event": "onClick", "action": item}))
                    except Exception:
                        pass
            return result
        return []

    @field_validator("children", mode="before")
    @classmethod
    def _coerce_children(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, AxureComponent):
                    result.append(item)
                elif isinstance(item, dict):
                    try:
                        result.append(AxureComponent.model_validate(item))
                    except Exception:
                        pass
            return result
        return []


class AxurePage(LenientModel):
    page_name: str = Field("Untitled", description="页面名称")
    page_size: Size = Field(default_factory=lambda: Size(width=1440, height=900))
    components: List[AxureComponent] = Field(default_factory=list, description="页面组件列表")
    page_url: Optional[str] = None

    @field_validator("page_name", mode="before")
    @classmethod
    def _coerce_name(cls, v):
        return str(v) if v is not None else "Untitled"

    @field_validator("page_url", mode="before")
    @classmethod
    def _coerce_str_opt(cls, v):
        return _to_str(v)

    @field_validator("components", mode="before")
    @classmethod
    def _coerce_components(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, AxureComponent):
                    result.append(item)
                elif isinstance(item, dict):
                    try:
                        result.append(AxureComponent.model_validate(item))
                    except Exception:
                        pass
            return result
        return []


class ParseResult(LenientModel):
    success: bool = True
    message: str = "解析成功"
    source_type: str = Field("", description="源文件类型: html/json")
    pages: List[AxurePage] = Field(default_factory=list)

    @field_validator("message", mode="before")
    @classmethod
    def _coerce_str(cls, v):
        return str(v) if v is not None else ""

    @field_validator("source_type", mode="before")
    @classmethod
    def _coerce_source_type(cls, v):
        return str(v) if v is not None else ""

    @field_validator("pages", mode="before")
    @classmethod
    def _coerce_pages(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, AxurePage):
                    result.append(item)
                elif isinstance(item, dict):
                    try:
                        result.append(AxurePage.model_validate(item))
                    except Exception:
                        pass
            return result
        return []


class GenerateRequest(LenientModel):
    pages: List[AxurePage] = Field(default_factory=list, description="要生成的页面数据")
    format: GenerateFormat = Field(GenerateFormat.FULL_PAGE, description="生成格式")
    include_interactions: bool = Field(True, description="是否包含交互JS")
    use_relative_position: bool = Field(True, description="使用相对定位(absolute)")

    @field_validator("format", mode="before")
    @classmethod
    def _coerce_format(cls, v):
        if v is None:
            return GenerateFormat.FULL_PAGE
        if isinstance(v, GenerateFormat):
            return v
        s = str(v).strip().lower().replace("-", "_")
        mapping = {
            "html_only": GenerateFormat.HTML_ONLY,
            "html": GenerateFormat.HTML_ONLY,
            "fragment": GenerateFormat.HTML_ONLY,
            "html_css": GenerateFormat.HTML_CSS,
            "css": GenerateFormat.HTML_CSS,
            "html+css": GenerateFormat.HTML_CSS,
            "full_page": GenerateFormat.FULL_PAGE,
            "full": GenerateFormat.FULL_PAGE,
            "page": GenerateFormat.FULL_PAGE,
        }
        if s in mapping:
            return mapping[s]
        try:
            return GenerateFormat(s)
        except ValueError:
            return GenerateFormat.FULL_PAGE

    @field_validator("include_interactions", "use_relative_position", mode="before")
    @classmethod
    def _coerce_bool(cls, v):
        if v is None:
            return True
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            return v.lower() not in ["false", "0", "no", "n", "off"]
        return True

    @field_validator("pages", mode="before")
    @classmethod
    def _coerce_pages(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, AxurePage):
                    result.append(item)
                elif isinstance(item, dict):
                    try:
                        result.append(AxurePage.model_validate(item))
                    except Exception:
                        pass
            return result
        return []


class GenerateResult(LenientModel):
    success: bool = True
    message: str = "生成成功"
    html: str = Field("", description="生成的HTML代码")
    css: Optional[str] = Field(None, description="生成的CSS代码")
    js: Optional[str] = Field(None, description="生成的JS代码")

    @field_validator("html", mode="before")
    @classmethod
    def _coerce_str(cls, v):
        return str(v) if v is not None else ""

    @field_validator("css", "js", "message", mode="before")
    @classmethod
    def _coerce_str_opt(cls, v):
        return _to_str(v)


AxureComponent.model_rebuild()
AxurePage.model_rebuild()
ParseResult.model_rebuild()
GenerateRequest.model_rebuild()
