from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import parser as parser_router
from app.routers import generator as generator_router

app = FastAPI(
    title="Axure 原型解析与代码生成器",
    description="将 Axure 导出的 HTML 或组件 JSON 解析为结构化数据，并生成可运行的 HTML/CSS 代码",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parser_router.router)
app.include_router(generator_router.router)


@app.get("/", tags=["info"])
async def root():
    return {
        "name": "Axure 原型解析与代码生成器",
        "version": "1.0.0",
        "description": "将 Axure 导出的 HTML 或组件 JSON 解析为结构化数据，并生成可运行的 HTML/CSS 代码",
        "docs": "/docs",
        "endpoints": {
            "parser": [
                "POST /api/parser/upload - 上传文件解析",
                "POST /api/parser/html - 传入HTML源码解析",
                "POST /api/parser/json - 传入JSON数据解析",
                "POST /api/parser/json/raw - 传入原始JSON字符串解析",
            ],
            "generator": [
                "POST /api/generator/generate - 按请求格式生成代码",
                "POST /api/generator/generate/html - 仅生成HTML片段",
                "POST /api/generator/generate/full - 生成完整HTML页面",
                "POST /api/generator/from-parse-result - 从解析结果直接生成",
                "POST /api/generator/download/html - 下载完整HTML文件",
                "POST /api/generator/download/css - 下载CSS文件",
            ],
        },
    }


@app.get("/health", tags=["info"])
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
