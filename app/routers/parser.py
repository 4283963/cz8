from typing import List, Optional, Any, Union
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request, Body
from fastapi.encoders import jsonable_encoder

from app.models.schemas import ParseResult, AxurePage
from app.services.axure_parser import parse_file

router = APIRouter(prefix="/api/parser", tags=["parser"])


SUPPORTED_HTML_EXTENSIONS = {".html", ".htm", ".xhtml"}
SUPPORTED_JSON_EXTENSIONS = {".json"}
KNOWN_EXTENSIONS = SUPPORTED_HTML_EXTENSIONS | SUPPORTED_JSON_EXTENSIONS


def _detect_source_type(filename: str = "", force_type: str = "", content_bytes: bytes = b"") -> str:
    if force_type:
        ft = force_type.lower().strip()
        if ft in ["html", "json", "htm", "xhtml"]:
            return "json" if ft == "json" else "html"
    if filename:
        lower_name = filename.lower()
        for ext in SUPPORTED_JSON_EXTENSIONS:
            if lower_name.endswith(ext):
                return "json"
        for ext in SUPPORTED_HTML_EXTENSIONS:
            if lower_name.endswith(ext):
                return "html"
    if content_bytes:
        try:
            preview = content_bytes[:500].decode("utf-8", errors="ignore").strip()
            if preview.startswith(("{", "[")):
                return "json"
            if "<html" in preview.lower() or "<!doctype" in preview.lower() or "<body" in preview.lower():
                return "html"
        except Exception:
            pass
    return "html"


@router.post("/upload", response_model=ParseResult)
async def parse_upload_file(
    request: Request,
) -> ParseResult:
    try:
        form = await request.form()
        file = form.get("file")
        source_type = form.get("source_type") or ""
        if file is None:
            raise HTTPException(status_code=400, detail="请上传文件（file 字段）")
        filename = getattr(file, "filename", "") or ""
        try:
            content = await file.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")
        detected_type = _detect_source_type(filename, source_type or "", content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求格式错误: {str(e)}")
    try:
        result = parse_file(content, detected_type, filename)
    except Exception as e:
        alt_type = "json" if detected_type == "html" else "html"
        try:
            result = parse_file(content, alt_type, filename)
            if result.success:
                result.message = f"自动切换为 {alt_type} 模式解析成功（原检测为 {detected_type}）: {result.message}"
                result.source_type = alt_type
                return result
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"解析失败，文件既不是有效的HTML也不是有效的JSON: {str(e)}")
    if not result.success and content:
        alt_type = "json" if detected_type == "html" else "html"
        alt_result = parse_file(content, alt_type, filename)
        if alt_result.success:
            alt_result.message = f"自动切换为 {alt_type} 模式解析成功（原检测为 {detected_type}）: {alt_result.message}"
            alt_result.source_type = alt_type
            return alt_result
    return result


@router.post("/html", response_model=ParseResult)
async def parse_html_content(
    request: Request,
) -> ParseResult:
    content = None
    filename = ""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        try:
            form = await request.form()
            content = form.get("content")
            filename = form.get("filename") or ""
        except Exception:
            pass
    if content is None:
        try:
            raw = await request.body()
            content = raw.decode("utf-8", errors="replace")
        except Exception:
            pass
    if not content or not str(content).strip():
        raise HTTPException(status_code=400, detail="HTML内容不能为空")
    result = parse_file(str(content), "html", str(filename or "content.html"))
    if not result.success:
        alt_result = parse_file(str(content), "json", str(filename or "content.json"))
        if alt_result.success:
            alt_result.message = f"内容为JSON格式，已自动切换解析: {alt_result.message}"
            alt_result.source_type = "json"
            return alt_result
    return result


@router.post("/json", response_model=ParseResult)
async def parse_json_data(
    request: Request,
) -> ParseResult:
    import json as json_lib
    content_type = request.headers.get("content-type", "")
    pages = None
    data = None
    raw_body = None
    try:
        raw_body = await request.body()
    except Exception:
        pass
    if raw_body and "application/json" in content_type:
        try:
            parsed = json_lib.loads(raw_body.decode("utf-8", errors="replace"))
            if isinstance(parsed, dict):
                if "pages" in parsed:
                    pages = parsed.get("pages")
                else:
                    data = parsed
            elif isinstance(parsed, list):
                pages = parsed
        except Exception:
            pass
    elif raw_body and ("multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type):
        try:
            form = await request.form()
            pages_str = form.get("pages")
            data_str = form.get("data")
            if pages_str:
                try:
                    pages = json_lib.loads(str(pages_str))
                except Exception:
                    pass
            if data_str and pages is None:
                try:
                    data = json_lib.loads(str(data_str))
                except Exception:
                    pass
        except Exception:
            pass
    if pages is not None:
        if isinstance(pages, list):
            coerced = []
            for p in pages:
                if isinstance(p, dict):
                    try:
                        coerced.append(AxurePage.model_validate(p))
                    except Exception:
                        pass
                elif isinstance(p, AxurePage):
                    coerced.append(p)
            pages_dicts = [p.model_dump() for p in coerced]
            json_content = json_lib.dumps({"pages": pages_dicts})
            result = parse_file(json_content, "json", "data.json")
            return result
    if data is not None:
        json_content = json_lib.dumps(data)
        result = parse_file(json_content, "json", "data.json")
        return result
    if raw_body:
        try:
            body_str = raw_body.decode("utf-8", errors="replace")
            result = parse_file(body_str, "json", "raw_body.json")
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")
    raise HTTPException(status_code=400, detail="请提供 pages 或 data 参数，或在请求体中传入JSON数据")


@router.post("/json/raw", response_model=ParseResult)
async def parse_json_raw(
    request: Request,
) -> ParseResult:
    content = None
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        try:
            form = await request.form()
            content = form.get("content")
        except Exception:
            pass
    if content is None:
        try:
            raw = await request.body()
            content = raw.decode("utf-8", errors="replace")
        except Exception:
            pass
    if not content or not str(content).strip():
        raise HTTPException(status_code=400, detail="JSON内容不能为空")
    result = parse_file(str(content), "json", "content.json")
    if not result.success:
        alt_result = parse_file(str(content), "html", "content.html")
        if alt_result.success:
            alt_result.message = f"内容为HTML格式，已自动切换解析: {alt_result.message}"
            alt_result.source_type = "html"
            return alt_result
    return result
