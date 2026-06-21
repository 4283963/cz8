from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form

from app.models.schemas import ParseResult, AxurePage
from app.services.axure_parser import parse_file

router = APIRouter(prefix="/api/parser", tags=["parser"])


SUPPORTED_HTML_EXTENSIONS = {".html", ".htm", ".xhtml"}
SUPPORTED_JSON_EXTENSIONS = {".json"}
SUPPORTED_EXTENSIONS = SUPPORTED_HTML_EXTENSIONS | SUPPORTED_JSON_EXTENSIONS


def _detect_source_type(filename: str, force_type: str = "") -> str:
    if force_type:
        return force_type.lower()
    lower_name = filename.lower()
    for ext in SUPPORTED_HTML_EXTENSIONS:
        if lower_name.endswith(ext):
            return "html"
    for ext in SUPPORTED_JSON_EXTENSIONS:
        if lower_name.endswith(ext):
            return "json"
    return "html"


@router.post("/upload", response_model=ParseResult)
async def parse_upload_file(
    file: UploadFile = File(..., description="Axure导出的HTML文件或组件JSON文件"),
    source_type: str = Form(
        default="",
        description="指定文件类型：html 或 json，留空则根据扩展名自动判断",
    ),
) -> ParseResult:
    filename = file.filename or ""
    detected_type = _detect_source_type(filename, source_type)
    lower_name = filename.lower()
    has_supported_ext = any(lower_name.endswith(ext) for ext in SUPPORTED_EXTENSIONS)
    if not source_type and not has_supported_ext:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型，请上传 {', '.join(sorted(SUPPORTED_EXTENSIONS))} 文件或显式指定 source_type",
        )
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")
    result = parse_file(content, detected_type, filename)
    return result


@router.post("/html", response_model=ParseResult)
async def parse_html_content(
    content: str = Form(..., description="HTML源码内容"),
    filename: str = Form(default="", description="可选的文件名标识"),
) -> ParseResult:
    if not content.strip():
        raise HTTPException(status_code=400, detail="HTML内容不能为空")
    result = parse_file(content, "html", filename or "content.html")
    return result


@router.post("/json", response_model=ParseResult)
async def parse_json_data(
    pages: List[AxurePage] = None,
    data: dict = None,
) -> ParseResult:
    import json as json_lib
    if pages is not None:
        import io
        pages_dicts = [p.model_dump() for p in pages]
        json_content = json_lib.dumps({"pages": pages_dicts})
        result = parse_file(json_content, "json", "data.json")
        return result
    if data is not None:
        json_content = json_lib.dumps(data)
        result = parse_file(json_content, "json", "data.json")
        return result
    raise HTTPException(status_code=400, detail="请提供 pages 或 data 参数")


@router.post("/json/raw", response_model=ParseResult)
async def parse_json_raw(
    content: str = Form(..., description="JSON格式的字符串内容"),
) -> ParseResult:
    if not content.strip():
        raise HTTPException(status_code=400, detail="JSON内容不能为空")
    result = parse_file(content, "json", "content.json")
    return result
