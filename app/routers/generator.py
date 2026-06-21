from typing import Optional, List, Any, Union
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, PlainTextResponse, FileResponse

from app.models.schemas import (
    GenerateRequest,
    GenerateResult,
    GenerateFormat,
    AxurePage,
    ParseResult,
)
from app.services.code_generator import generate_code
from app.utils.helpers import safe_filename

router = APIRouter(prefix="/api/generator", tags=["generator"])


def _coerce_pages(pages: Any) -> List[AxurePage]:
    if not pages:
        return []
    if isinstance(pages, list):
        result = []
        for item in pages:
            if isinstance(item, AxurePage):
                result.append(item)
            elif isinstance(item, dict):
                try:
                    result.append(AxurePage.model_validate(item))
                except Exception:
                    pass
        return result
    return []


def _coerce_bool(v: Any, default: bool = True) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.lower() not in ["false", "0", "no", "n", "off"]
    return default


def _coerce_format(v: Any) -> GenerateFormat:
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
        return GenerateFormat(str(v))
    except (ValueError, TypeError):
        return GenerateFormat.FULL_PAGE


@router.post("/generate", response_model=GenerateResult)
async def generate_code_endpoint(
    request: Request,
) -> GenerateResult:
    try:
        content_type = request.headers.get("content-type", "")
        raw = None
        try:
            raw_body = await request.body()
            if raw_body:
                import json
                raw = json.loads(raw_body.decode("utf-8", errors="replace"))
        except Exception:
            pass
        pages = []
        fmt = GenerateFormat.FULL_PAGE
        include_interactions = True
        use_relative_position = True
        if raw and isinstance(raw, dict):
            pages = _coerce_pages(raw.get("pages"))
            fmt = _coerce_format(raw.get("format"))
            include_interactions = _coerce_bool(raw.get("include_interactions"), True)
            use_relative_position = _coerce_bool(raw.get("use_relative_position"), True)
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            try:
                form = await request.form()
                pages_str = form.get("pages")
                if pages_str:
                    import json
                    try:
                        pages_data = json.loads(str(pages_str))
                        pages = _coerce_pages(pages_data)
                    except Exception:
                        pass
                fmt = _coerce_format(form.get("format"))
                include_interactions = _coerce_bool(form.get("include_interactions"), True)
                use_relative_position = _coerce_bool(form.get("use_relative_position"), True)
            except Exception:
                pass
        req = GenerateRequest(
            pages=pages,
            format=fmt,
            include_interactions=include_interactions,
            use_relative_position=use_relative_position,
        )
        if not req.pages:
            raise HTTPException(status_code=400, detail="pages 参数不能为空")
        result = generate_code(req)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求参数错误: {str(e)}")


@router.post("/generate/html")
async def generate_html_only(
    request: Request,
) -> PlainTextResponse:
    try:
        content_type = request.headers.get("content-type", "")
        pages = []
        try:
            raw_body = await request.body()
            if raw_body:
                import json
                raw = json.loads(raw_body.decode("utf-8", errors="replace"))
                if isinstance(raw, list):
                    pages = _coerce_pages(raw)
                elif isinstance(raw, dict):
                    pages = _coerce_pages(raw.get("pages"))
        except Exception:
            pass
        if not pages and ("application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type):
            try:
                form = await request.form()
                pages_str = form.get("pages")
                if pages_str:
                    import json
                    try:
                        pages_data = json.loads(str(pages_str))
                        pages = _coerce_pages(pages_data)
                    except Exception:
                        pass
            except Exception:
                pass
        if not pages:
            raise HTTPException(status_code=400, detail="pages 不能为空")
        req = GenerateRequest(
            pages=pages,
            format=GenerateFormat.HTML_ONLY,
            include_interactions=False,
            use_relative_position=True,
        )
        result = generate_code(req)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        return PlainTextResponse(result.html, media_type="text/html; charset=utf-8")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求参数错误: {str(e)}")


@router.post("/generate/full")
async def generate_full_page(
    request: Request,
) -> Response:
    try:
        content_type = request.headers.get("content-type", "")
        pages = []
        include_interactions = True
        try:
            raw_body = await request.body()
            if raw_body:
                import json
                raw = json.loads(raw_body.decode("utf-8", errors="replace"))
                if isinstance(raw, list):
                    pages = _coerce_pages(raw)
                elif isinstance(raw, dict):
                    pages = _coerce_pages(raw.get("pages"))
                    if raw.get("include_interactions") is not None:
                        include_interactions = _coerce_bool(raw.get("include_interactions"))
        except Exception:
            pass
        if not pages and ("application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type):
            try:
                form = await request.form()
                pages_str = form.get("pages")
                if pages_str:
                    import json
                    try:
                        pages_data = json.loads(str(pages_str))
                        pages = _coerce_pages(pages_data)
                    except Exception:
                        pass
                if form.get("include_interactions") is not None:
                    include_interactions = _coerce_bool(form.get("include_interactions"))
            except Exception:
                pass
        if not pages:
            raise HTTPException(status_code=400, detail="pages 不能为空")
        req = GenerateRequest(
            pages=pages,
            format=GenerateFormat.FULL_PAGE,
            include_interactions=include_interactions,
            use_relative_position=True,
        )
        result = generate_code(req)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        return Response(result.html, media_type="text/html; charset=utf-8")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求参数错误: {str(e)}")


@router.post("/from-parse-result", response_model=GenerateResult)
async def generate_from_parse_result(
    request: Request,
) -> GenerateResult:
    try:
        content_type = request.headers.get("content-type", "")
        pages = []
        fmt = GenerateFormat.FULL_PAGE
        include_interactions = True
        try:
            raw_body = await request.body()
            if raw_body:
                import json
                raw = json.loads(raw_body.decode("utf-8", errors="replace"))
                if isinstance(raw, dict):
                    pages = _coerce_pages(raw.get("pages"))
                    if raw.get("format"):
                        fmt = _coerce_format(raw.get("format"))
                    if raw.get("include_interactions") is not None:
                        include_interactions = _coerce_bool(raw.get("include_interactions"))
                    if not pages and raw.get("success") and isinstance(raw.get("pages"), list):
                        pages = _coerce_pages(raw.get("pages"))
        except Exception:
            pass
        if not pages and ("application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type):
            try:
                form = await request.form()
                pr_str = form.get("parse_result")
                if pr_str:
                    import json
                    try:
                        pr_data = json.loads(str(pr_str))
                        pages = _coerce_pages(pr_data.get("pages"))
                    except Exception:
                        pass
                if form.get("format"):
                    fmt = _coerce_format(form.get("format"))
                if form.get("include_interactions") is not None:
                    include_interactions = _coerce_bool(form.get("include_interactions"))
            except Exception:
                pass
        if not pages:
            raise HTTPException(status_code=400, detail="解析结果无效，无法生成代码")
        req = GenerateRequest(
            pages=pages,
            format=fmt,
            include_interactions=include_interactions,
            use_relative_position=True,
        )
        result = generate_code(req)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求参数错误: {str(e)}")


@router.post("/download/html")
async def download_html(
    request: Request,
) -> FileResponse:
    import tempfile
    import os
    try:
        content_type = request.headers.get("content-type", "")
        pages = []
        filename = "generated_page.html"
        include_interactions = True
        try:
            raw_body = await request.body()
            if raw_body:
                import json
                raw = json.loads(raw_body.decode("utf-8", errors="replace"))
                if isinstance(raw, list):
                    pages = _coerce_pages(raw)
                elif isinstance(raw, dict):
                    pages = _coerce_pages(raw.get("pages"))
                    if raw.get("filename"):
                        filename = str(raw.get("filename"))
                    if raw.get("include_interactions") is not None:
                        include_interactions = _coerce_bool(raw.get("include_interactions"))
        except Exception:
            pass
        query_params = request.query_params
        if query_params.get("filename"):
            filename = str(query_params.get("filename"))
        if query_params.get("include_interactions") is not None:
            include_interactions = _coerce_bool(query_params.get("include_interactions"))
        if not pages and ("application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type):
            try:
                form = await request.form()
                pages_str = form.get("pages")
                if pages_str:
                    import json
                    try:
                        pages_data = json.loads(str(pages_str))
                        pages = _coerce_pages(pages_data)
                    except Exception:
                        pass
                if form.get("filename"):
                    filename = str(form.get("filename"))
                if form.get("include_interactions") is not None:
                    include_interactions = _coerce_bool(form.get("include_interactions"))
            except Exception:
                pass
        if not pages:
            raise HTTPException(status_code=400, detail="pages 不能为空")
        req = GenerateRequest(
            pages=pages,
            format=GenerateFormat.FULL_PAGE,
            include_interactions=include_interactions,
            use_relative_position=True,
        )
        result = generate_code(req)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        safe_name = safe_filename(filename)
        if not safe_name.lower().endswith(".html"):
            safe_name += ".html"
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, safe_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(result.html)
        return FileResponse(
            path=file_path,
            filename=safe_name,
            media_type="text/html; charset=utf-8",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求参数错误: {str(e)}")


@router.post("/download/css")
async def download_css(
    request: Request,
) -> FileResponse:
    import tempfile
    import os
    try:
        content_type = request.headers.get("content-type", "")
        pages = []
        filename = "styles.css"
        try:
            raw_body = await request.body()
            if raw_body:
                import json
                raw = json.loads(raw_body.decode("utf-8", errors="replace"))
                if isinstance(raw, list):
                    pages = _coerce_pages(raw)
                elif isinstance(raw, dict):
                    pages = _coerce_pages(raw.get("pages"))
                    if raw.get("filename"):
                        filename = str(raw.get("filename"))
        except Exception:
            pass
        query_params = request.query_params
        if query_params.get("filename"):
            filename = str(query_params.get("filename"))
        if not pages and ("application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type):
            try:
                form = await request.form()
                pages_str = form.get("pages")
                if pages_str:
                    import json
                    try:
                        pages_data = json.loads(str(pages_str))
                        pages = _coerce_pages(pages_data)
                    except Exception:
                        pass
                if form.get("filename"):
                    filename = str(form.get("filename"))
            except Exception:
                pass
        if not pages:
            raise HTTPException(status_code=400, detail="pages 不能为空")
        req = GenerateRequest(
            pages=pages,
            format=GenerateFormat.HTML_CSS,
            include_interactions=False,
            use_relative_position=True,
        )
        result = generate_code(req)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        safe_name = safe_filename(filename)
        if not safe_name.lower().endswith(".css"):
            safe_name += ".css"
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, safe_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(result.css or "")
        return FileResponse(
            path=file_path,
            filename=safe_name,
            media_type="text/css; charset=utf-8",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求参数错误: {str(e)}")
