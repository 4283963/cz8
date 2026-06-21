from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


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


class Position(BaseModel):
    x: float = Field(0, description="组件左上角X坐标")
    y: float = Field(0, description="组件左上角Y坐标")


class Size(BaseModel):
    width: float = Field(0, description="组件宽度")
    height: float = Field(0, description="组件高度")


class BorderStyle(BaseModel):
    width: Optional[float] = None
    style: Optional[str] = None
    color: Optional[str] = None
    radius: Optional[float] = None


class TextStyle(BaseModel):
    font_family: Optional[str] = None
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    color: Optional[str] = None
    text_align: Optional[str] = None
    line_height: Optional[float] = None


class ComponentStyle(BaseModel):
    background_color: Optional[str] = None
    opacity: Optional[float] = None
    border: Optional[BorderStyle] = None
    text_style: Optional[TextStyle] = None
    padding: Optional[Dict[str, float]] = None
    shadow: Optional[bool] = None


class InteractionEvent(str, Enum):
    ON_CLICK = "onClick"
    ON_MOUSE_ENTER = "onMouseEnter"
    ON_MOUSE_LEAVE = "onMouseLeave"
    ON_CHANGE = "onChange"
    ON_FOCUS = "onFocus"
    ON_BLUR = "onBlur"


class Interaction(BaseModel):
    event: InteractionEvent
    action: str = Field(..., description="触发动作描述，如跳转、显示隐藏等")
    target: Optional[str] = None


class AxureComponent(BaseModel):
    id: str = Field(..., description="组件唯一标识")
    name: Optional[str] = Field(None, description="组件名称")
    component_type: ComponentType = Field(ComponentType.UNKNOWN, description="组件类型")
    position: Position
    size: Size
    style: Optional[ComponentStyle] = None
    text: Optional[str] = Field(None, description="组件显示的文本内容")
    placeholder: Optional[str] = Field(None, description="占位符文本")
    default_value: Optional[str] = Field(None, description="默认值")
    interactions: List[Interaction] = Field(default_factory=list, description="交互事件列表")
    children: List["AxureComponent"] = Field(default_factory=list, description="子组件")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="原始数据备用")


class AxurePage(BaseModel):
    page_name: str = Field(..., description="页面名称")
    page_size: Size = Field(default_factory=lambda: Size(width=1440, height=900))
    components: List[AxureComponent] = Field(default_factory=list, description="页面组件列表")
    page_url: Optional[str] = None


class ParseResult(BaseModel):
    success: bool = True
    message: str = "解析成功"
    source_type: str = Field(..., description="源文件类型: html/json")
    pages: List[AxurePage] = Field(default_factory=list)


class GenerateFormat(str, Enum):
    HTML_ONLY = "html_only"
    HTML_CSS = "html_css"
    FULL_PAGE = "full_page"


class GenerateRequest(BaseModel):
    pages: List[AxurePage] = Field(..., description="要生成的页面数据")
    format: GenerateFormat = Field(GenerateFormat.FULL_PAGE, description="生成格式")
    include_interactions: bool = Field(True, description="是否包含交互JS")
    use_relative_position: bool = Field(True, description="使用相对定位(absolute)")


class GenerateResult(BaseModel):
    success: bool = True
    message: str = "生成成功"
    html: str = Field(..., description="生成的HTML代码")
    css: Optional[str] = Field(None, description="生成的CSS代码")
    js: Optional[str] = Field(None, description="生成的JS代码")
