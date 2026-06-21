from fastapi import APIRouter, HTTPException, Query
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


@router.post("/generate", response_model=GenerateResult)
async def generate_code_endpoint(
    request: GenerateRequest,
) -> GenerateResult:
    if not request.pages:
        raise HTTPException(status_code=400, detail="pages 参数不能为空")
    result = generate_code(request)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    return result


@router.post("/generate/html")
async def generate_html_only(
    pages: list[AxurePage],
) -> PlainTextResponse:
    if not pages:
        raise HTTPException(status_code=400, detail="pages 不能为空")
    request = GenerateRequest(
        pages=pages,
        format=GenerateFormat.HTML_ONLY,
        include_interactions=False,
        use_relative_position=True,
    )
    result = generate_code(request)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    return PlainTextResponse(result.html, media_type="text/html; charset=utf-8")


@router.post("/generate/full")
async def generate_full_page(
    pages: list[AxurePage],
    include_interactions: bool = Query(True, description="是否包含交互JS"),
) -> Response:
    if not pages:
        raise HTTPException(status_code=400, detail="pages 不能为空")
    request = GenerateRequest(
        pages=pages,
        format=GenerateFormat.FULL_PAGE,
        include_interactions=include_interactions,
        use_relative_position=True,
    )
    result = generate_code(request)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    return Response(result.html, media_type="text/html; charset=utf-8")


@router.post("/from-parse-result", response_model=GenerateResult)
async def generate_from_parse_result(
    parse_result: ParseResult,
    format: GenerateFormat = Query(
        GenerateFormat.FULL_PAGE, description="生成格式"
    ),
    include_interactions: bool = Query(True, description="是否包含交互JS"),
) -> GenerateResult:
    if not parse_result.success or not parse_result.pages:
        raise HTTPException(status_code=400, detail="解析结果无效，无法生成代码")
    request = GenerateRequest(
        pages=parse_result.pages,
        format=format,
        include_interactions=include_interactions,
        use_relative_position=True,
    )
    result = generate_code(request)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    return result


@router.post("/download/html")
async def download_html(
    pages: list[AxurePage],
    filename: str = Query("generated_page.html", description="下载文件名"),
    include_interactions: bool = Query(True, description="是否包含交互JS"),
):
    import tempfile
    import os
    if not pages:
        raise HTTPException(status_code=400, detail="pages 不能为空")
    request = GenerateRequest(
        pages=pages,
        format=GenerateFormat.FULL_PAGE,
        include_interactions=include_interactions,
        use_relative_position=True,
    )
    result = generate_code(request)
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


@router.post("/download/css")
async def download_css(
    pages: list[AxurePage],
    filename: str = Query("styles.css", description="下载文件名"),
):
    import tempfile
    import os
    if not pages:
        raise HTTPException(status_code=400, detail="pages 不能为空")
    request = GenerateRequest(
        pages=pages,
        format=GenerateFormat.HTML_CSS,
        include_interactions=False,
        use_relative_position=True,
    )
    result = generate_code(request)
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
