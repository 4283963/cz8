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
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return ParseResult(
                success=False,
                message=f"JSON解析错误: {str(e)}",
                source_type="json",
                pages=[],
            )
        pages = []
        if isinstance(data, list):
            for idx, page_data in enumerate(data):
                page = self._json_to_page(page_data, f"{filename or 'page'}_{idx + 1}")
                if page:
                    pages.append(page)
        elif isinstance(data, dict):
            if "pages" in data and isinstance(data["pages"], list):
                for idx, page_data in enumerate(data["pages"]):
                    page = self._json_to_page(page_data, page_data.get("name", f"page_{idx + 1}"))
                    if page:
                        pages.append(page)
            else:
                page = self._json_to_page(data, filename or "page_1")
                if page:
                    pages.append(page)
        return ParseResult(
            success=True,
            message=f"解析成功，共 {len(pages)} 个页面",
            source_type="json",
            pages=pages,
        )

    def _json_to_page(self, page_data: Dict[str, Any], page_name: str) -> Optional[AxurePage]:
        try:
            name = page_data.get("page_name") or page_data.get("name") or page_name
            size_data = page_data.get("page_size") or page_data.get("size") or {}
            page_size = Size(
                width=float(size_data.get("width", 1440)),
                height=float(size_data.get("height", 900)),
            )
            page_url = page_data.get("page_url")
            components_data = page_data.get("components") or page_data.get("widgets") or page_data.get("elements") or []
            components = [self._json_to_component(c) for c in components_data]
            components = [c for c in components if c is not None]
            return AxurePage(
                page_name=name,
                page_size=page_size,
                components=components,
                page_url=page_url,
            )
        except Exception:
            return None

    def _json_to_component(self, comp_data: Dict[str, Any]) -> Optional[AxureComponent]:
        try:
            comp_id = comp_data.get("id") or generate_component_id()
            comp_type_str = comp_data.get("component_type") or comp_data.get("type") or "unknown"
            try:
                component_type = ComponentType(comp_type_str)
            except ValueError:
                component_type = ComponentType.UNKNOWN
            pos_data = comp_data.get("position") or {}
            position = Position(
                x=float(pos_data.get("x", 0)),
                y=float(pos_data.get("y", 0)),
            )
            size_data = comp_data.get("size") or {}
            size = Size(
                width=float(size_data.get("width", 0)),
                height=float(size_data.get("height", 0)),
            )
            style = self._parse_json_style(comp_data.get("style") or {})
            interactions = []
            for ia in comp_data.get("interactions") or []:
                interactions.append(self._parse_json_interaction(ia))
            children = []
            for child in comp_data.get("children") or []:
                child_comp = self._json_to_component(child)
                if child_comp:
                    children.append(child_comp)
            return AxureComponent(
                id=comp_id,
                name=comp_data.get("name"),
                component_type=component_type,
                position=position,
                size=size,
                style=style,
                text=comp_data.get("text"),
                placeholder=comp_data.get("placeholder"),
                default_value=comp_data.get("default_value"),
                interactions=interactions,
                children=children,
                raw_data=comp_data,
            )
        except Exception:
            return None

    def _parse_json_style(self, style_data: Dict[str, Any]) -> Optional[ComponentStyle]:
        if not style_data:
            return None
        border_data = style_data.get("border")
        border = None
        if border_data:
            border = BorderStyle(
                width=border_data.get("width"),
                style=border_data.get("style"),
                color=border_data.get("color"),
                radius=border_data.get("radius"),
            )
        text_data = style_data.get("text_style")
        text_style = None
        if text_data:
            text_style = TextStyle(
                font_family=text_data.get("font_family"),
                font_size=text_data.get("font_size"),
                font_weight=text_data.get("font_weight"),
                color=text_data.get("color"),
                text_align=text_data.get("text_align"),
                line_height=text_data.get("line_height"),
            )
        return ComponentStyle(
            background_color=parse_hex_color(style_data.get("background_color") or style_data.get("bg_color") or ""),
            opacity=style_data.get("opacity"),
            border=border,
            text_style=text_style,
            padding=style_data.get("padding"),
            shadow=style_data.get("shadow"),
        )

    def _parse_json_interaction(self, ia_data: Dict[str, Any]) -> Interaction:
        event_str = ia_data.get("event") or ia_data.get("trigger") or "onClick"
        try:
            event = InteractionEvent(event_str)
        except ValueError:
            event = InteractionEvent.ON_CLICK
        return Interaction(
            event=event,
            action=ia_data.get("action") or ia_data.get("handler") or "",
            target=ia_data.get("target"),
        )

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
