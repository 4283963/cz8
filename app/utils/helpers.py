import re
import uuid
import hashlib
from typing import Optional, Dict, Any, Tuple
from app.models.schemas import ComponentType


AXURE_CLASS_PATTERNS: Dict[ComponentType, list] = {
    ComponentType.BUTTON: [
        r"_button\b", r"\bButton\b", r"\bbutton\b", r"\bbtn[_\-]", r"widget_button"
    ],
    ComponentType.TEXT_INPUT: [
        r"text_input", r"textinput", r"\bTextBox\b", r"\btextbox\b", r"\bTextField\b", r"\bTextInput\b"
    ],
    ComponentType.TEXT_AREA: [
        r"text_area", r"textarea", r"\bTextArea\b", r"\bMultiLine\b"
    ],
    ComponentType.LABEL: [
        r"\bLabel\b", r"\bStaticText\b", r"\bHeading\b", r"\bParagraph\b", r"\blabel_text\b"
    ],
    ComponentType.IMAGE: [
        r"\bImage\b", r"\bPicture\b", r"\bImageBox\b"
    ],
    ComponentType.CHECKBOX: [
        r"checkbox", r"\bCheckBox\b", r"\bCheck\b", r"Checkbox"
    ],
    ComponentType.RADIO: [
        r"\bRadioButton\b", r"\bRadio\b", r"radio_button"
    ],
    ComponentType.DROPDOWN: [
        r"dropdown", r"\bDropDown\b", r"\bComboBox\b", r"\bListBox\b"
    ],
    ComponentType.LINK: [
        r"hyperlink", r"\bHyperLink\b", r"\bAnchor\b"
    ],
    ComponentType.TABLE: [
        r"\bTable\b", r"\bGrid\b", r"\bDataTable\b"
    ],
    ComponentType.DYNAMIC_PANEL: [
        r"dynamic_panel", r"\bDynamicPanel\b", r"dyn_panel"
    ],
    ComponentType.REPEATER: [
        r"\bRepeater\b", r"repeater"
    ],
    ComponentType.RECTANGLE: [
        r"\bRectangle\b", r"\bBox\b", r"\brect\b"
    ],
}


COMPONENT_TYPE_PRIORITY = [
    ComponentType.CHECKBOX,
    ComponentType.RADIO,
    ComponentType.TEXT_AREA,
    ComponentType.DROPDOWN,
    ComponentType.LINK,
    ComponentType.IMAGE,
    ComponentType.TABLE,
    ComponentType.BUTTON,
    ComponentType.TEXT_INPUT,
    ComponentType.LABEL,
    ComponentType.REPEATER,
    ComponentType.DYNAMIC_PANEL,
    ComponentType.RECTANGLE,
    ComponentType.UNKNOWN,
]


def generate_component_id(prefix: str = "comp") -> str:
    short_hash = hashlib.md5(uuid.uuid4().bytes).hexdigest()[:8]
    return f"{prefix}_{short_hash}"


def sanitize_css_identifier(name: str) -> str:
    if not name:
        return generate_component_id("cls")
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    sanitized = re.sub(r"^[^a-zA-Z]", "_", sanitized)
    return sanitized[:50] if len(sanitized) > 50 else sanitized


def parse_style_string(style_str: str) -> Dict[str, str]:
    result = {}
    if not style_str:
        return result
    declarations = style_str.split(";")
    for decl in declarations:
        if ":" in decl:
            key, value = decl.split(":", 1)
            key = key.strip().lower().replace("-", "_")
            value = value.strip()
            if value:
                result[key] = value
    return result


def extract_size_from_style(style: Dict[str, str]) -> Tuple[Optional[float], Optional[float]]:
    width = None
    height = None
    if "width" in style:
        width = parse_pixel_value(style["width"])
    if "height" in style:
        height = parse_pixel_value(style["height"])
    return width, height


def extract_position_from_style(style: Dict[str, str]) -> Tuple[Optional[float], Optional[float]]:
    x = None
    y = None
    if "left" in style:
        x = parse_pixel_value(style["left"])
    if "top" in style:
        y = parse_pixel_value(style["top"])
    return x, y


def parse_pixel_value(value: str) -> Optional[float]:
    if not value:
        return None
    match = re.match(r"([-+]?\d*\.?\d+)\s*(px|pt|em|rem|%)?", value.strip())
    if match:
        num = float(match.group(1))
        unit = match.group(2)
        if unit == "pt":
            num = num * 1.333
        elif unit == "em" or unit == "rem":
            num = num * 16
        return round(num, 2)
    return None


def parse_hex_color(color: str) -> Optional[str]:
    if not color:
        return None
    color = color.strip()
    if color.startswith("#"):
        if len(color) == 4:
            r, g, b = color[1], color[2], color[3]
            return f"#{r}{r}{g}{g}{b}{b}"
        if len(color) == 7:
            return color.lower()
    rgb_match = re.match(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color, re.IGNORECASE)
    if rgb_match:
        r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
        return f"#{r:02x}{g:02x}{b:02x}"
    rgba_match = re.match(r"rgba\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)", color, re.IGNORECASE)
    if rgba_match:
        r, g, b = int(rgba_match.group(1)), int(rgba_match.group(2)), int(rgba_match.group(3))
        return f"#{r:02x}{g:02x}{b:02x}"
    return color.lower() if color else None


def detect_component_type(class_names: str, text: str = "", tag_name: str = "", attrs: Dict[str, Any] = None) -> ComponentType:
    class_lower = class_names.lower()
    attrs = attrs or {}
    input_type = attrs.get("type", "").lower()
    if tag_name.lower() == "input" and input_type == "checkbox":
        return ComponentType.CHECKBOX
    if tag_name.lower() == "input" and input_type == "radio":
        return ComponentType.RADIO
    if tag_name.lower() == "textarea":
        return ComponentType.TEXT_AREA
    if tag_name.lower() == "select":
        return ComponentType.DROPDOWN
    if tag_name.lower() == "a":
        return ComponentType.LINK
    if tag_name.lower() == "img":
        return ComponentType.IMAGE
    if tag_name.lower() == "table":
        return ComponentType.TABLE
    if tag_name.lower() == "input" and input_type in ["text", "password", "email", "number", "tel", "url", "search"]:
        return ComponentType.TEXT_INPUT
    if tag_name.lower() == "button":
        return ComponentType.BUTTON
    for comp_type in COMPONENT_TYPE_PRIORITY:
        if comp_type == ComponentType.UNKNOWN:
            continue
        patterns = AXURE_CLASS_PATTERNS.get(comp_type, [])
        for pattern in patterns:
            if re.search(pattern, class_names, re.IGNORECASE):
                return comp_type
    if tag_name.lower() == "div" and class_lower:
        if "panel" in class_lower or "container" in class_lower:
            return ComponentType.DYNAMIC_PANEL
        return ComponentType.RECTANGLE
    if tag_name.lower() == "span" or tag_name.lower() == "p" or tag_name.lower().startswith("h"):
        return ComponentType.LABEL
    return ComponentType.UNKNOWN


def safe_filename(name: str) -> str:
    if not name:
        return "untitled"
    return re.sub(r"[^\w\-.]", "_", name).strip("_") or "untitled"
