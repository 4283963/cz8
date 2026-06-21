import json
import re
from typing import List, Dict, Any, Optional, Union
from io import BytesIO
from bs4 import BeautifulSoup, Tag

from app.models.schemas import (
    ComponentType,
    Position,
    Size,
    BorderStyle,
    TextStyle,
    ComponentStyle,
    InteractionEvent,
    Interaction,
    AxureComponent,
    AxurePage,
    ParseResult,
)
from app.utils.helpers import (
    generate_component_id,
    parse_style_string,
    extract_size_from_style,
    extract_position_from_style,
    parse_pixel_value,
    parse_hex_color,
    detect_component_type,
)


class AxureParser:
    def __init__(self):
        self._used_ids = set()

    def parse(self, content: Union[str, bytes], source_type: str, filename: str = "") -> ParseResult:
        try:
            if source_type.lower() == "json":
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
                return self._parse_json(content, filename)
            else:
                if isinstance(content, bytes):
                    content = content.decode("utf-8", errors="replace")
                return self._parse_html(content, filename)
        except Exception as e:
            return ParseResult(
                success=False,
                message=f"解析失败: {str(e)}",
                source_type=source_type,
                pages=[],
            )

    def _parse_json(self, content: str, filename: str) -> ParseResult:
        try:
            content = content.strip()
            if content.startswith(("'", '"')) and len(content) >= 2:
                content = content[1:-1]
            data = json.loads(content)
        except json.JSONDecodeError as e:
            fixed = self._try_fix_json(content)
            if fixed is not None:
                data = fixed
            else:
                return ParseResult(
                    success=False,
                    message=f"JSON解析错误: {str(e)}",
                    source_type="json",
                    pages=[],
                )
        pages = []
        if isinstance(data, list):
            for idx, page_data in enumerate(data):
                if not isinstance(page_data, dict):
                    continue
                page = self._json_to_page(page_data, f"{filename or 'page'}_{idx + 1}")
                if page:
                    pages.append(page)
        elif isinstance(data, dict):
            pages_data = None
            for key in ["pages", "page", "screens", "views", "data"]:
                val = data.get(key)
                if isinstance(val, list):
                    pages_data = val
                    break
            if pages_data:
                for idx, page_data in enumerate(pages_data):
                    if not isinstance(page_data, dict):
                        continue
                    page = self._json_to_page(page_data, page_data.get("name") or page_data.get("page_name") or f"page_{idx + 1}")
                    if page:
                        pages.append(page)
            else:
                page = self._json_to_page(data, filename or "page_1")
                if page:
                    pages.append(page)
        if not pages:
            return ParseResult(
                success=False,
                message="未解析到有效的页面数据",
                source_type="json",
                pages=[],
            )
        return ParseResult(
            success=True,
            message=f"解析成功，共 {len(pages)} 个页面",
            source_type="json",
            pages=pages,
        )

    def _try_fix_json(self, content: str) -> Optional[Any]:
        try:
            fixed = content.replace("'", '"')
            import re
            fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
            fixed = re.sub(r'(\w+)(\s*:)', r'"\1"\2', fixed)
            return json.loads(fixed)
        except Exception:
            return None

    def _to_float(self, val: Any, default: float = 0.0) -> float:
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def _to_int(self, val: Any, default: int = 0) -> int:
        if val is None:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _to_dict(self, val: Any) -> Dict[str, Any]:
        if isinstance(val, dict):
            return val
        return {}

    def _to_list(self, val: Any) -> List[Any]:
        if isinstance(val, list):
            return val
        return []

    def _json_to_page(self, page_data: Any, page_name: str) -> Optional[AxurePage]:
        try:
            if not isinstance(page_data, dict):
                page_data = {}
            name = page_data.get("page_name") or page_data.get("name") or page_data.get("title") or page_name
            size_data = self._to_dict(page_data.get("page_size") or page_data.get("size") or page_data.get("canvas") or {})
            page_size = Size(
                width=self._to_float(size_data.get("width"), 1440),
                height=self._to_float(size_data.get("height"), 900),
            )
            page_url = page_data.get("page_url") or page_data.get("url")
            comp_keys = ["components", "widgets", "elements", "items", "children", "nodes"]
            components_data = []
            for k in comp_keys:
                val = page_data.get(k)
                if isinstance(val, list) and val:
                    components_data = val
                    break
            components = []
            for c in components_data:
                comp = self._json_to_component(c)
                if comp:
                    components.append(comp)
            return AxurePage(
                page_name=str(name) if name else page_name,
                page_size=page_size,
                components=components,
                page_url=str(page_url) if page_url else None,
            )
        except Exception:
            return None

    def _json_to_component(self, comp_data: Any) -> Optional[AxureComponent]:
        try:
            if not isinstance(comp_data, dict):
                return None
            comp_id = comp_data.get("id") or comp_data.get("widgetId") or comp_data.get("uid") or generate_component_id()
            comp_type_str = comp_data.get("component_type") or comp_data.get("type") or comp_data.get("widgetType") or "unknown"
            try:
                component_type = ComponentType(str(comp_type_str))
            except (ValueError, TypeError):
                component_type = ComponentType.UNKNOWN
            pos_data = self._to_dict(comp_data.get("position") or comp_data.get("pos") or comp_data.get("location") or {})
            if not pos_data:
                pos_data = {
                    "x": self._to_float(comp_data.get("x") or comp_data.get("left"), 0),
                    "y": self._to_float(comp_data.get("y") or comp_data.get("top"), 0),
                }
            position = Position(
                x=self._to_float(pos_data.get("x") or pos_data.get("left"), 0),
                y=self._to_float(pos_data.get("y") or pos_data.get("top"), 0),
            )
            size_data = self._to_dict(comp_data.get("size") or {})
            if not size_data:
                size_data = {
                    "width": self._to_float(comp_data.get("width"), 0),
                    "height": self._to_float(comp_data.get("height"), 0),
                }
            size = Size(
                width=self._to_float(size_data.get("width"), 0),
                height=self._to_float(size_data.get("height"), 0),
            )
            style = self._parse_json_style(comp_data.get("style") or comp_data.get("styles") or {})
            interactions = []
            for ia in self._to_list(comp_data.get("interactions") or comp_data.get("events") or comp_data.get("actions") or []):
                parsed = self._parse_json_interaction(ia)
                if parsed:
                    interactions.append(parsed)
            children = []
            for child in self._to_list(comp_data.get("children") or comp_data.get("items") or comp_data.get("nested") or []):
                child_comp = self._json_to_component(child)
                if child_comp:
                    children.append(child_comp)
            text = comp_data.get("text") or comp_data.get("label") or comp_data.get("content")
            placeholder = comp_data.get("placeholder") or comp_data.get("hint")
            default_value = comp_data.get("default_value") or comp_data.get("value") or comp_data.get("default")
            return AxureComponent(
                id=str(comp_id),
                name=str(comp_data.get("name") or comp_data.get("label")) if comp_data.get("name") or comp_data.get("label") else None,
                component_type=component_type,
                position=position,
                size=size,
                style=style,
                text=str(text) if text is not None else None,
                placeholder=str(placeholder) if placeholder is not None else None,
                default_value=str(default_value) if default_value is not None else None,
                interactions=interactions,
                children=children,
                raw_data=comp_data,
            )
        except Exception:
            return None

    def _parse_json_style(self, style_data: Any) -> Optional[ComponentStyle]:
        if not style_data or not isinstance(style_data, dict):
            return None
        has_style = False
        try:
            border_data = style_data.get("border") or style_data.get("borderStyle")
            border = None
            if border_data:
                if isinstance(border_data, dict):
                    border = BorderStyle(
                        width=self._to_float(border_data.get("width") or border_data.get("borderWidth"), None),
                        style=str(border_data.get("style") or border_data.get("borderStyle")) if border_data.get("style") or border_data.get("borderStyle") else None,
                        color=parse_hex_color(str(border_data.get("color") or border_data.get("borderColor") or "")) if (border_data.get("color") or border_data.get("borderColor")) else None,
                        radius=self._to_float(border_data.get("radius") or border_data.get("borderRadius") or border_data.get("cornerRadius"), None),
                    )
                elif isinstance(border_data, str):
                    border_parts = border_data.split()
                    bw, bs, bc = None, None, None
                    for p in border_parts:
                        if "px" in p or re.match(r"^\d+(\.\d+)?$", p):
                            bw = self._to_float(p, None)
                        elif p in ["solid", "dashed", "dotted", "double", "none"]:
                            bs = p
                        else:
                            bc = parse_hex_color(p) or p
                    border = BorderStyle(width=bw, style=bs, color=bc, radius=None)
                if border:
                    has_style = True
            text_data = style_data.get("text_style") or style_data.get("textStyle") or style_data.get("font")
            text_style = None
            if text_data:
                if isinstance(text_data, dict):
                    ts = TextStyle(
                        font_family=str(text_data.get("font_family") or text_data.get("fontFamily") or text_data.get("font")) if (text_data.get("font_family") or text_data.get("fontFamily") or text_data.get("font")) else None,
                        font_size=self._to_float(text_data.get("font_size") or text_data.get("fontSize"), None),
                        font_weight=str(text_data.get("font_weight") or text_data.get("fontWeight")) if (text_data.get("font_weight") or text_data.get("fontWeight")) else None,
                        color=parse_hex_color(str(text_data.get("color") or "")) if text_data.get("color") else None,
                        text_align=str(text_data.get("text_align") or text_data.get("textAlign") or text_data.get("align")) if (text_data.get("text_align") or text_data.get("textAlign") or text_data.get("align")) else None,
                        line_height=self._to_float(text_data.get("line_height") or text_data.get("lineHeight"), None),
                    )
                    has_style = True
                    any_set = any([ts.font_family, ts.font_size is not None, ts.font_weight, ts.color, ts.text_align, ts.line_height is not None])
                    if any_set:
                        text_style = ts
            bg_color = parse_hex_color(str(style_data.get("background_color") or style_data.get("bg_color") or style_data.get("backgroundColor") or style_data.get("bg") or ""))
            bg_color = bg_color if bg_color and bg_color.strip() and bg_color not in ["transparent", "none"] else None
            opacity = style_data.get("opacity")
            if opacity is not None:
                try:
                    opacity = float(opacity)
                except (ValueError, TypeError):
                    opacity = None
            padding = style_data.get("padding")
            shadow = style_data.get("shadow") or style_data.get("boxShadow")
            if bg_color or opacity is not None or border or text_style or padding or shadow:
                has_style = True
            if not has_style:
                return None
            return ComponentStyle(
                background_color=bg_color,
                opacity=opacity,
                border=border,
                text_style=text_style,
                padding=padding if isinstance(padding, dict) else None,
                shadow=bool(shadow) if shadow is not None else None,
            )
        except Exception:
            return None

    def _parse_json_interaction(self, ia_data: Any) -> Optional[Interaction]:
        try:
            if not isinstance(ia_data, dict):
                if isinstance(ia_data, str):
                    return Interaction(
                        event=InteractionEvent.ON_CLICK,
                        action=str(ia_data),
                    )
                return None
            event_str = ia_data.get("event") or ia_data.get("trigger") or ia_data.get("on") or "onClick"
            try:
                event = InteractionEvent(str(event_str))
            except (ValueError, TypeError):
                event = InteractionEvent.ON_CLICK
            action = ia_data.get("action") or ia_data.get("handler") or ia_data.get("do") or ia_data.get("description") or ""
            target = ia_data.get("target") or ia_data.get("to") or ia_data.get("link")
            return Interaction(
                event=event,
                action=str(action),
                target=str(target) if target else None,
            )
        except Exception:
            return None

    def _parse_html(self, content: str, filename: str) -> ParseResult:
        soup = BeautifulSoup(content, "lxml")
        pages = []
        page_name = filename or "page_1"
        title_tag = soup.find("title")
        if title_tag and title_tag.text.strip():
            page_name = title_tag.text.strip()
        components = self._extract_components_from_html(soup)
        page_size = self._extract_page_size(soup, components)
        page = AxurePage(
            page_name=page_name,
            page_size=page_size,
            components=components,
        )
        pages.append(page)
        return ParseResult(
            success=True,
            message=f"解析成功，提取 {len(components)} 个组件",
            source_type="html",
            pages=pages,
        )

    def _extract_page_size(self, soup: BeautifulSoup, components: List[AxureComponent]) -> Size:
        width = 1440
        height = 900
        if components:
            max_x = max(c.position.x + c.size.width for c in components if c.size) or 0
            max_y = max(c.position.y + c.size.height for c in components if c.size) or 0
            if max_x > 0:
                width = max(int(max_x + 100), 800)
            if max_y > 0:
                height = max(int(max_y + 100), 600)
        body = soup.find("body")
        if body and body.get("style"):
            style = parse_style_string(body["style"])
            w, h = extract_size_from_style(style)
            if w:
                width = int(w)
            if h:
                height = int(h)
        return Size(width=width, height=height)

    def _extract_components_from_html(self, soup: BeautifulSoup) -> List[AxureComponent]:
        self._used_ids = set()
        components = []
        body = soup.find("body")
        if not body:
            return components
        candidates = []
        for tag in body.find_all(recursive=True):
            if self._is_component_candidate(tag):
                candidates.append(tag)
        processed = set()
        for tag in candidates:
            if id(tag) in processed:
                continue
            component = self._html_tag_to_component(tag, processed)
            if component:
                components.append(component)
        if not components:
            for tag in body.find_all(["div", "input", "textarea", "button", "a", "select", "img", "table"]):
                if id(tag) in processed:
                    continue
                component = self._html_tag_to_component(tag, processed)
                if component and (component.size.width > 10 and component.size.height > 10):
                    components.append(component)
        return components

    def _is_component_candidate(self, tag: Tag) -> bool:
        if not hasattr(tag, "attrs"):
            return False
        class_attr = " ".join(tag.get("class", []) or [])
        style_attr = tag.get("style", "") or ""
        data_attrs = [k for k in tag.attrs if k.startswith("data-")]
        if re.search(r"(?:u\d+|widget|component|element|panel|button|input|text|label|image|dropdown)", class_attr, re.I):
            return True
        if "position: absolute" in style_attr or "position:absolute" in style_attr:
            w, h = extract_size_from_style(parse_style_string(style_attr))
            if w and h and w > 15 and h > 10:
                return True
        if data_attrs and (style_attr or class_attr):
            return True
        return False

    def _html_tag_to_component(self, tag: Tag, processed: set) -> Optional[AxureComponent]:
        try:
            processed.add(id(tag))
            class_attr = " ".join(tag.get("class", []) or [])
            style_attr = tag.get("style", "") or ""
            style = parse_style_string(style_attr)
            pos_x, pos_y = extract_position_from_style(style)
            w, h = extract_size_from_style(style)
            x = float(pos_x or self._try_extract_from_transform(style_attr, "x") or 0)
            y = float(pos_y or self._try_extract_from_transform(style_attr, "y") or 0)
            width = float(w or tag.get("width") or self._parse_width_height_from_style(style_attr, "width") or 0)
            height = float(h or tag.get("height") or self._parse_width_height_from_style(style_attr, "height") or 0)
            tag_name = tag.name.lower() if tag.name else ""
            attrs = dict(tag.attrs)
            comp_type = detect_component_type(class_attr, tag.get_text()[:50], tag_name, attrs)
            comp_id = tag.get("id") or generate_component_id()
            if comp_id in self._used_ids:
                comp_id = generate_component_id()
            self._used_ids.add(comp_id)
            name = tag.get("data-name") or tag.get("data-label") or tag.get("name") or None
            text = self._extract_tag_text(tag)
            placeholder = tag.get("placeholder")
            default_value = tag.get("value")
            comp_style = self._html_style_to_component_style(style, tag)
            interactions = self._extract_interactions(tag)
            children = []
            for child in tag.find_all(recursive=False):
                if self._is_component_candidate(child):
                    child_comp = self._html_tag_to_component(child, processed)
                    if child_comp:
                        children.append(child_comp)
            if comp_type == ComponentType.UNKNOWN and width < 20 and height < 20:
                return None
            return AxureComponent(
                id=comp_id,
                name=name,
                component_type=comp_type,
                position=Position(x=x, y=y),
                size=Size(width=width, height=height),
                style=comp_style,
                text=text,
                placeholder=placeholder,
                default_value=default_value,
                interactions=interactions,
                children=children,
            )
        except Exception:
            return None

    def _extract_tag_text(self, tag: Tag) -> Optional[str]:
        tag_name = tag.name.lower() if tag.name else ""
        if tag_name in ["input", "select"]:
            return tag.get("value") or tag.get("placeholder")
        if tag_name == "textarea":
            return tag.get("value") or tag.get_text()
        direct_text = "".join([c.strip() for c in tag.find_all(string=True, recursive=False)])
        if direct_text:
            return direct_text.strip()
        all_text = tag.get_text(" ", strip=True)
        if all_text and len(all_text) < 200:
            return all_text
        return None

    def _html_style_to_component_style(self, style: Dict[str, str], tag: Tag) -> Optional[ComponentStyle]:
        if not style:
            return None
        has_style = False
        background_color = None
        if "background_color" in style or "background" in style:
            bg = style.get("background_color") or style.get("background", "")
            parsed = parse_hex_color(bg)
            if parsed and not parsed.startswith("rgba(") and not parsed.startswith("rgb("):
                background_color = parsed
                has_style = True
            elif bg and bg not in ["transparent", "none"]:
                background_color = bg
                has_style = True
        opacity = None
        if "opacity" in style:
            try:
                opacity = float(style["opacity"])
                has_style = True
            except (ValueError, TypeError):
                pass
        border = None
        border_parts = {}
        for key in ["border_width", "border_style", "border_color", "border_radius"]:
            if key in style:
                border_parts[key] = style[key]
        if "border" in style:
            border_str = style["border"]
            parts = border_str.split()
            for p in parts:
                if "px" in p or re.match(r"^\d+(\.\d+)?$", p):
                    border_parts["border_width"] = p
                elif p in ["solid", "dashed", "dotted", "double", "none"]:
                    border_parts["border_style"] = p
                else:
                    border_parts["border_color"] = parse_hex_color(p) or p
        if border_parts:
            border = BorderStyle(
                width=parse_pixel_value(border_parts.get("border_width", "")),
                style=border_parts.get("border_style"),
                color=parse_hex_color(border_parts.get("border_color", "") or "") if border_parts.get("border_color") else None,
                radius=parse_pixel_value(border_parts.get("border_radius", "")),
            )
            has_style = True
        text_style = None
        ts_keys = ["font_family", "font_size", "font_weight", "color", "text_align", "line_height"]
        ts_data = {k: style[k] for k in ts_keys if k in style}
        if tag.name and tag.name.lower() in ["input", "textarea", "select"] and not ts_data:
            pass
        if ts_data:
            text_style = TextStyle(
                font_family=ts_data.get("font_family", "").strip("'\" ") or None,
                font_size=parse_pixel_value(ts_data.get("font_size", "")),
                font_weight=ts_data.get("font_weight"),
                color=parse_hex_color(ts_data.get("color", "") or "") if ts_data.get("color") else None,
                text_align=ts_data.get("text_align"),
                line_height=parse_pixel_value(ts_data.get("line_height", "")) if ts_data.get("line_height") else None,
            )
            has_style = True
        padding = None
        if "padding" in style:
            padding = {"all": parse_pixel_value(style["padding"]) or 0}
            has_style = True
        shadow = "box_shadow" in style
        if not has_style:
            return None
        return ComponentStyle(
            background_color=background_color,
            opacity=opacity,
            border=border,
            text_style=text_style,
            padding=padding,
            shadow=shadow,
        )

    def _extract_interactions(self, tag: Tag) -> List[Interaction]:
        interactions = []
        event_mappings = [
            ("onclick", InteractionEvent.ON_CLICK),
            ("onmouseenter", InteractionEvent.ON_MOUSE_ENTER),
            ("onmouseleave", InteractionEvent.ON_MOUSE_LEAVE),
            ("onchange", InteractionEvent.ON_CHANGE),
            ("onfocus", InteractionEvent.ON_FOCUS),
            ("onblur", InteractionEvent.ON_BLUR),
            ("onmouseover", InteractionEvent.ON_MOUSE_ENTER),
            ("onmouseout", InteractionEvent.ON_MOUSE_LEAVE),
        ]
        for attr, event in event_mappings:
            handler = tag.get(attr)
            if handler:
                interactions.append(Interaction(
                    event=event,
                    action=handler.strip(),
                ))
        data_events = [k for k in tag.attrs if k.startswith("data-") and ("event" in k or "action" in k or "on" in k.lower())]
        for de in data_events:
            val = tag.get(de)
            if val:
                interactions.append(Interaction(
                    event=InteractionEvent.ON_CLICK,
                    action=val.strip(),
                ))
        href = tag.get("href")
        if tag.name and tag.name.lower() == "a" and href:
            interactions.append(Interaction(
                event=InteractionEvent.ON_CLICK,
                action=f"navigate:{href}",
                target=href,
            ))
        return interactions

    def _try_extract_from_transform(self, style_str: str, axis: str) -> Optional[float]:
        match = re.search(r"transform\s*:\s*translate\s*\(\s*([-\d.]+)\s*px?\s*,\s*([-\d.]+)\s*px?\s*\)", style_str, re.I)
        if match:
            if axis == "x":
                try:
                    return float(match.group(1))
                except ValueError:
                    return None
            else:
                try:
                    return float(match.group(2))
                except ValueError:
                    return None
        return None

    def _parse_width_height_from_style(self, style_str: str, dim: str) -> Optional[float]:
        match = re.search(rf"{dim}\s*:\s*([-+]?\d*\.?\d+)\s*px", style_str, re.I)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None


_parser_instance: Optional[AxureParser] = None


def get_parser() -> AxureParser:
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = AxureParser()
    return _parser_instance


def parse_file(content: Union[str, bytes], source_type: str, filename: str = "") -> ParseResult:
    parser = get_parser()
    return parser.parse(content, source_type, filename)
