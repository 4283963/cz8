from typing import List, Dict, Any, Optional, Tuple
from html import escape

from app.models.schemas import (
    ComponentType,
    ComponentStyle,
    InteractionEvent,
    Interaction,
    AxureComponent,
    AxurePage,
    GenerateRequest,
    GenerateFormat,
    GenerateResult,
)
from app.utils.helpers import sanitize_css_identifier, generate_component_id


class CodeGenerator:
    def __init__(self):
        self._class_map: Dict[str, str] = {}

    def generate(self, request: GenerateRequest) -> GenerateResult:
        try:
            html_parts = []
            css_parts = []
            js_parts = []
            for page in request.pages:
                page_html, page_css, page_js = self._generate_page(
                    page, request.use_relative_position, request.include_interactions
                )
                html_parts.append(page_html)
                css_parts.append(page_css)
                js_parts.append(page_js)
            combined_html = "\n".join(html_parts)
            combined_css = "\n".join(css_parts)
            combined_js = "\n".join(js_parts)
            if request.format == GenerateFormat.HTML_ONLY:
                return GenerateResult(
                    success=True,
                    message="生成成功",
                    html=combined_html,
                    css=None,
                    js=None,
                )
            elif request.format == GenerateFormat.HTML_CSS:
                return GenerateResult(
                    success=True,
                    message="生成成功",
                    html=combined_html,
                    css=combined_css if combined_css else None,
                    js=None,
                )
            else:
                full_html = self._wrap_full_page(combined_html, combined_css, combined_js, request.pages)
                return GenerateResult(
                    success=True,
                    message="生成成功",
                    html=full_html,
                    css=combined_css if combined_css else None,
                    js=combined_js if combined_js else None,
                )
        except Exception as e:
            return GenerateResult(
                success=False,
                message=f"生成失败: {str(e)}",
                html="",
                css=None,
                js=None,
            )

    def _generate_page(
        self,
        page: AxurePage,
        use_relative: bool,
        include_interactions: bool,
    ) -> Tuple[str, str, str]:
        page_class = sanitize_css_identifier(f"page_{page.page_name}")
        page_css = []
        page_js = []
        style_declarations = []
        if use_relative:
            style_declarations.append("position: relative")
        style_declarations.append(f"width: {page.page_size.width}px")
        style_declarations.append(f"height: {page.page_size.height}px")
        style_declarations.append("margin: 0 auto")
        style_declarations.append("background-color: #ffffff")
        style_declarations.append("overflow: hidden")
        page_css.append(f".{page_class} {{")
        page_css.append("  " + ";\n  ".join(style_declarations) + ";")
        page_css.append("}")
        components_html = []
        for comp in page.components:
            comp_html, comp_css, comp_js = self._generate_component(
                comp, use_relative, include_interactions, parent_class=page_class
            )
            components_html.append(comp_html)
            if comp_css:
                page_css.append(comp_css)
            if comp_js:
                page_js.append(comp_js)
        page_html = f'<div class="{page_class}">\n' + "\n".join(components_html) + "\n</div>"
        return page_html, "\n".join(page_css), "\n".join(page_js)

    def _generate_component(
        self,
        comp: AxureComponent,
        use_relative: bool,
        include_interactions: bool,
        parent_class: str = "",
    ) -> Tuple[str, str, str]:
        comp_key = f"{parent_class}_{comp.id}"
        css_class = sanitize_css_identifier(f"comp_{comp.id}")
        self._class_map[comp_key] = css_class
        css = self._generate_component_css(comp, css_class, use_relative)
        html = self._generate_component_html(comp, css_class, include_interactions)
        js = ""
        if include_interactions and comp.interactions:
            js = self._generate_component_js(comp, css_class)
        if comp.children:
            children_html_parts = []
            children_css_parts = [css] if css else []
            children_js_parts = [js] if js else []
            for child in comp.children:
                child_html, child_css, child_js = self._generate_component(
                    child, use_relative, include_interactions, parent_class=comp_key
                )
                children_html_parts.append(child_html)
                if child_css:
                    children_css_parts.append(child_css)
                if child_js:
                    children_js_parts.append(child_js)
            inner_html = "\n".join(children_html_parts)
            html = html.replace(">{content}<", ">\n{content}\n<", 1)
            html = html.format(content=inner_html)
            if not "{content}" in html:
                close_pos = html.rfind("<")
                if close_pos > 0 and html.endswith(">"):
                    tag_end = html.rfind(">", close_pos)
                    html = html[:tag_end] + "\n" + inner_html + "\n" + html[tag_end:]
            css = "\n".join(children_css_parts)
            js = "\n".join(children_js_parts)
        return html, css, js

    def _generate_component_css(
        self, comp: AxureComponent, css_class: str, use_relative: bool
    ) -> str:
        declarations = []
        if use_relative:
            declarations.append("position: absolute")
            declarations.append(f"left: {comp.position.x}px")
            declarations.append(f"top: {comp.position.y}px")
        declarations.append(f"width: {comp.size.width}px")
        declarations.append(f"height: {comp.size.height}px")
        style = comp.style
        if style:
            if style.background_color:
                declarations.append(f"background-color: {style.background_color}")
            if style.opacity is not None:
                declarations.append(f"opacity: {style.opacity}")
            if style.shadow:
                declarations.append("box-shadow: 0 2px 4px rgba(0,0,0,0.1)")
            if style.padding:
                if "all" in style.padding:
                    declarations.append(f"padding: {style.padding['all']}px")
                else:
                    p_top = style.padding.get("top", 0)
                    p_right = style.padding.get("right", 0)
                    p_bottom = style.padding.get("bottom", 0)
                    p_left = style.padding.get("left", 0)
                    declarations.append(f"padding: {p_top}px {p_right}px {p_bottom}px {p_left}px")
            if style.border:
                border_parts = []
                if style.border.width is not None:
                    border_parts.append(f"{style.border.width}px")
                if style.border.style:
                    border_parts.append(style.border.style)
                elif border_parts:
                    border_parts.append("solid")
                if style.border.color:
                    border_parts.append(style.border.color)
                elif border_parts:
                    border_parts.append("#cccccc")
                if border_parts:
                    declarations.append(f"border: {' '.join(border_parts)}")
                if style.border.radius is not None:
                    declarations.append(f"border-radius: {style.border.radius}px")
            if style.text_style:
                ts = style.text_style
                if ts.font_family:
                    declarations.append(f"font-family: '{ts.font_family}', sans-serif")
                if ts.font_size is not None:
                    declarations.append(f"font-size: {ts.font_size}px")
                if ts.font_weight:
                    declarations.append(f"font-weight: {ts.font_weight}")
                if ts.color:
                    declarations.append(f"color: {ts.color}")
                if ts.text_align:
                    declarations.append(f"text-align: {ts.text_align}")
                if ts.line_height is not None:
                    declarations.append(f"line-height: {ts.line_height}px")
        declarations.append("box-sizing: border-box")
        lines = [f".{css_class} {{"]
        lines.append("  " + ";\n  ".join(declarations) + ";")
        lines.append("}")
        return "\n".join(lines)

    def _generate_component_html(
        self, comp: AxureComponent, css_class: str, include_interactions: bool
    ) -> str:
        attrs = {
            "id": comp.id,
            "class": css_class,
        }
        if comp.name:
            attrs["data-name"] = comp.name
        attrs["data-type"] = comp.component_type.value
        if include_interactions and comp.interactions:
            for ia in comp.interactions:
                attr_name = self._event_to_attr(ia.event)
                if attr_name:
                    handler = self._escape_js_string(ia.action)
                    attrs[attr_name] = handler
        text_content = comp.text or ""
        if comp.component_type == ComponentType.BUTTON:
            return self._build_tag("button", attrs, escape(text_content) or "按钮")
        elif comp.component_type == ComponentType.TEXT_INPUT:
            attrs["type"] = "text"
            if comp.placeholder:
                attrs["placeholder"] = comp.placeholder
            if comp.default_value:
                attrs["value"] = comp.default_value
            return self._build_self_closing_tag("input", attrs)
        elif comp.component_type == ComponentType.TEXT_AREA:
            if comp.placeholder:
                attrs["placeholder"] = comp.placeholder
            return self._build_tag("textarea", attrs, comp.default_value or "")
        elif comp.component_type == ComponentType.LABEL:
            return self._build_tag("div", attrs, escape(text_content) or "标签")
        elif comp.component_type == ComponentType.IMAGE:
            attrs["src"] = comp.default_value or "data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect fill='%23eee' width='100' height='100'/%3E%3Ctext fill='%23aaa' font-family='Arial' font-size='14' x='50' y='55' text-anchor='middle'%3EImage%3C/text%3E%3C/svg%3E"
            attrs["alt"] = comp.name or text_content or "image"
            return self._build_self_closing_tag("img", attrs)
        elif comp.component_type == ComponentType.CHECKBOX:
            attrs["type"] = "checkbox"
            if comp.default_value:
                attrs["checked"] = "checked"
            checkbox_tag = self._build_self_closing_tag("input", attrs)
            wrapper_attrs = {"class": css_class, "style": f"position: absolute; left: {comp.position.x}px; top: {comp.position.y}px; display: inline-flex; align-items: center;"}
            label_text = escape(text_content) or ""
            return f'<div {self._build_attrs_string(wrapper_attrs)}>{checkbox_tag}<span style="margin-left: 4px;">{label_text}</span></div>'
        elif comp.component_type == ComponentType.RADIO:
            attrs["type"] = "radio"
            attrs["name"] = comp.name or "radio_group"
            if comp.default_value:
                attrs["checked"] = "checked"
            radio_tag = self._build_self_closing_tag("input", attrs)
            wrapper_attrs = {"class": css_class, "style": f"position: absolute; left: {comp.position.x}px; top: {comp.position.y}px; display: inline-flex; align-items: center;"}
            label_text = escape(text_content) or ""
            return f'<div {self._build_attrs_string(wrapper_attrs)}>{radio_tag}<span style="margin-left: 4px;">{label_text}</span></div>'
        elif comp.component_type == ComponentType.DROPDOWN:
            inner_options = '<option value="">请选择...</option>'
            if comp.default_value:
                inner_options = f'<option value="" selected>{escape(comp.default_value)}</option>'
            return self._build_tag("select", attrs, inner_options)
        elif comp.component_type == ComponentType.LINK:
            attrs["href"] = comp.default_value or "javascript:void(0)"
            return self._build_tag("a", attrs, escape(text_content) or "链接")
        elif comp.component_type == ComponentType.TABLE:
            return self._build_tag("table", attrs, "<tr><td>单元格</td></tr>")
        elif comp.component_type == ComponentType.DYNAMIC_PANEL or comp.component_type == ComponentType.REPEATER:
            return self._build_tag("div", attrs, "")
        elif comp.component_type == ComponentType.RECTANGLE:
            return self._build_tag("div", attrs, "")
        else:
            return self._build_tag("div", attrs, escape(text_content) if len(text_content) < 100 else "")

    def _generate_component_js(self, comp: AxureComponent, css_class: str) -> str:
        lines = []
        for ia in comp.interactions:
            event_name = ia.event.value
            action = ia.action
            target = ia.target or ""
            js_action = self._interaction_to_js(action, target)
            lines.append(f"document.getElementById('{comp.id}').addEventListener('{self._event_to_js_name(ia.event)}', function(e) {{")
            lines.append(f"  {js_action}")
            lines.append("});")
        return "\n".join(lines)

    def _interaction_to_js(self, action: str, target: str) -> str:
        if action.startswith("navigate:"):
            url = action[9:]
            return f"window.location.href = '{self._escape_js_string(url)}';"
        if action.startswith("show:"):
            target_id = action[5:]
            return f"var el = document.getElementById('{self._escape_js_string(target_id)}'); if(el) el.style.display = 'block';"
        if action.startswith("hide:"):
            target_id = action[5:]
            return f"var el = document.getElementById('{self._escape_js_string(target_id)}'); if(el) el.style.display = 'none';"
        if action.startswith("alert:"):
            msg = action[6:]
            return f"alert('{self._escape_js_string(msg)}');"
        if target and target.startswith("http"):
            return f"window.open('{self._escape_js_string(target)}', '_blank');"
        return f"console.log('{self._escape_js_string(action)}', e);"

    def _event_to_attr(self, event: InteractionEvent) -> str:
        mapping = {
            InteractionEvent.ON_CLICK: "onclick",
            InteractionEvent.ON_MOUSE_ENTER: "onmouseenter",
            InteractionEvent.ON_MOUSE_LEAVE: "onmouseleave",
            InteractionEvent.ON_CHANGE: "onchange",
            InteractionEvent.ON_FOCUS: "onfocus",
            InteractionEvent.ON_BLUR: "onblur",
        }
        return mapping.get(event, "")

    def _event_to_js_name(self, event: InteractionEvent) -> str:
        mapping = {
            InteractionEvent.ON_CLICK: "click",
            InteractionEvent.ON_MOUSE_ENTER: "mouseenter",
            InteractionEvent.ON_MOUSE_LEAVE: "mouseleave",
            InteractionEvent.ON_CHANGE: "change",
            InteractionEvent.ON_FOCUS: "focus",
            InteractionEvent.ON_BLUR: "blur",
        }
        return mapping.get(event, "click")

    def _build_tag(self, tag_name: str, attrs: Dict[str, str], content: str) -> str:
        attrs_str = self._build_attrs_string(attrs)
        return f"<{tag_name} {attrs_str}>{content}</{tag_name}>"

    def _build_self_closing_tag(self, tag_name: str, attrs: Dict[str, str]) -> str:
        attrs_str = self._build_attrs_string(attrs)
        return f"<{tag_name} {attrs_str}/>"

    def _build_attrs_string(self, attrs: Dict[str, Any]) -> str:
        parts = []
        for key, value in attrs.items():
            if value is not None:
                if isinstance(value, bool):
                    if value:
                        parts.append(str(key))
                else:
                    escaped_value = str(value).replace('"', "&quot;")
                    parts.append(f'{key}="{escaped_value}"')
        return " ".join(parts)

    def _escape_js_string(self, s: str) -> str:
        return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")

    def _wrap_full_page(
        self,
        body_html: str,
        css_code: str,
        js_code: str,
        pages: List[AxurePage],
    ) -> str:
        page_title = pages[0].page_name if pages else "Generated Page"
        css_block = ""
        if css_code:
            css_block = f"<style>\n/* Auto-generated CSS */\n* {{\n  margin: 0;\n  padding: 0;\n}}\nbody {{\n  background-color: #f5f5f5;\n  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;\n  padding: 20px;\n}}\n{css_code}\n</style>"
        js_block = ""
        if js_code:
            js_block = f"<script>\ndocument.addEventListener('DOMContentLoaded', function() {{\n{js_code}\n}});\n</script>"
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(page_title)}</title>
  {css_block}
</head>
<body>
{body_html}
{js_block}
</body>
</html>"""


_generator_instance: Optional[CodeGenerator] = None


def get_generator() -> CodeGenerator:
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = CodeGenerator()
    return _generator_instance


def generate_code(request: GenerateRequest) -> GenerateResult:
    generator = get_generator()
    return generator.generate(request)
