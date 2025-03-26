from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional
import httpx
import json
import asyncio
from typing import Dict, Any
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from openai import OpenAI
import re
import logging
from datetime import datetime

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

app = FastAPI()

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 设置模板目录
templates = Jinja2Templates(directory="templates")

# 存储任务状态的内存字典
tasks: Dict[str, Dict[str, Any]] = {}

# 硅基流动API配置
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "your_siliconflow_api_key_here")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

# 阿里云百炼API配置
DEFAULT_BAILIAN_API_KEY = os.getenv("DEFAULT_BAILIAN_API_KEY", "your_default_key_here")

# 创建硅基流动客户端
client = OpenAI(
    api_key=SILICONFLOW_API_KEY,
    base_url=SILICONFLOW_BASE_URL
)

# 系统提示词
SYSTEM_PROMPT = """
你是一个专业的营销文案撰写专家。请按照以下格式生成营销文案：

标题：[简短有力的主标题，不超过30字]
副标题：[补充说明主标题，不超过30字]
正文：[详细描述产品特点和优势，不超过50字]
提示词：[用于生成图片的中文提示词，描述期望的视觉效果，不超过50字]

请确保每个部分都有内容，并严格按照这个格式输出。
"""

class PosterRequest(BaseModel):
    title: str
    sub_title: str
    body_text: str
    prompt_text_zh: str
    wh_ratios: str
    lora_name: str
    api_key: Optional[str] = None

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
async def generate_poster(request: Request):
    data = await request.json()
    title: str = data["title"]
    sub_title: str = data["sub_title"]
    body_text: str = data["body_text"]
    prompt_text_zh: str = data["prompt_text_zh"]
    wh_ratios: str = data["wh_ratios"]
    lora_name: str = data["lora_name"]
    api_key: Optional[str] = data.get("api_key")
    try:
        # 验证必填字段
        if not all([title, sub_title, body_text, prompt_text_zh, wh_ratios, lora_name]):
            return JSONResponse(
                status_code=400,
                content={"error": "所有字段都是必填的"}
            )

        # 使用提供的API Key或默认值
        used_api_key = api_key if api_key else DEFAULT_BAILIAN_API_KEY

        # 构建请求数据
        data = {
            "model": "wanx-poster-generation-v1",
            "input": {
                "title": title,
                "sub_title": sub_title,
                "body_text": body_text,
                "prompt_text_zh": prompt_text_zh,
                "wh_ratios": wh_ratios,
                "lora_name": lora_name,
                "lora_weight": 0.8,
                "ctrl_ratio": 0.7,
                "ctrl_step": 0.7,
                "generate_mode": "generate",
                "generate_num": 1
            },
            "parameters": {}
        }
        
        # 调用阿里云API
        async with httpx.AsyncClient() as client:
            try:
                print(f"API REQUEST: {data}")
                response = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                    headers={
                        "Authorization": f"Bearer {used_api_key}",
                        "Content-Type": "application/json",
                        "X-DashScope-Async": "enable"
                    },
                    json=data,
                    timeout=30.0
                )
                
                response_text = response.text
        
                print(f"API RESPONSE: {response_text}")
                
                if response.status_code != 200:
                    return JSONResponse(
                        status_code=400,
                        content={"error": f"API调用失败: {response_text}"}
                    )
                
                result = response.json()
                task_id = result.get("output", {}).get("task_id")
                
                if not task_id:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "未获取到任务ID"}
                    )
                
                # 存储任务信息
                tasks[task_id] = {
                    "status": "PENDING",
                    "data": data,
                    "result": None,
                    "api_key": used_api_key  # 存储API密钥用于后续查询
                }
                
                return {"task_id": task_id}
                
            except httpx.RequestError as e:
                return JSONResponse(
                    status_code=500,
                    content={"error": f"请求失败: {str(e)}"}
                )
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"生成失败: {str(e)}"}
        )

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in tasks:
        return JSONResponse(
            status_code=404,
            content={"error": "任务不存在"}
        )
    
    task = tasks[task_id]
    
    # 如果任务已经完成或失败，直接返回结果
    if task["status"] in ["SUCCEEDED", "FAILED"]:
        return {
            "status": task["status"],
            "result": task["result"],
            "error_message": task.get("error_message")
        }
    
    # 如果任务还在进行中，查询最新状态
    try:
        async with httpx.AsyncClient() as client:
            # 使用存储的API key或默认值
            used_api_key = task.get('api_key') or DEFAULT_BAILIAN_API_KEY
            
            response = await client.get(
                f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {used_api_key}"},
                timeout=30.0
            )
            
            if response.status_code != 200:
                task["status"] = "FAILED"
                task["error_message"] = "API调用失败"
                return {
                    "status": "FAILED",
                    "error_message": "API调用失败"
                }
            
            result = response.json()
            status = result.get("output", {}).get("task_status")
            
            if status == "SUCCEEDED":
                task["status"] = "SUCCEEDED"
                # 获取render_urls中的第一张图片URL
                render_urls = result.get("output", {}).get("render_urls", [])
                if render_urls:
                    task["result"] = {
                        "image_url": render_urls[0]
                    }
                else:
                    task["status"] = "FAILED"
                    task["error_message"] = "未获取到生成的图片URL"
                    return {
                        "status": "FAILED",
                        "error_message": "未获取到生成的图片URL"
                    }
                return {
                    "status": "SUCCEEDED",
                    "result": task["result"]
                }
            elif status == "FAILED":
                task["status"] = "FAILED"
                task["error_message"] = result.get("output", {}).get("message", "任务失败")
                return {
                    "status": "FAILED",
                    "error_message": task["error_message"]
                }
            else:
                # 任务仍在进行中
                return {
                    "status": "PENDING",
                    "message": "任务正在处理中"
                }
                
    except Exception as e:
        task["status"] = "FAILED"
        task["error_message"] = str(e)
        return {
            "status": "FAILED",
            "error_message": str(e)
        }

def parse_generated_text(text: str) -> dict:
    """
    解析AI生成的文本，提取标题、副标题、正文和提示词
    """
    try:
        logger.info("开始解析文本")
        # 初始化结果字典
        result = {
            "title": "",
            "sub_title": "",
            "body_text": "",
            "prompt_text_zh": ""
        }
        
        # 按行分割文本
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 解析每一行
            if line.startswith("标题："):
                result["title"] = line.replace("标题：", "").strip()
            elif line.startswith("副标题："):
                result["sub_title"] = line.replace("副标题：", "").strip()
            elif line.startswith("正文："):
                result["body_text"] = line.replace("正文：", "").strip()
            elif line.startswith("提示词："):
                result["prompt_text_zh"] = line.replace("提示词：", "").strip()
        
        logger.info(f"解析结果: {result}")
        
        # 验证所有必需字段都已填充
        if not all(result.values()):
            missing_fields = [k for k, v in result.items() if not v]
            logger.warning(f"部分字段未解析到: {missing_fields}")
            raise ValueError(f"生成的文本格式不完整，缺少字段: {', '.join(missing_fields)}")
            
        return result
        
    except Exception as e:
        logger.error(f"解析文本时发生错误: {str(e)}")
        logger.exception(e)
        raise

@app.post("/generate_prompt")
async def generate_prompt(request: Request):
    try:
        logger.info("开始处理生成提示词请求")
        
        data = await request.json()
        product_desc = data.get("product_desc", "")
        logger.info(f"收到的产品描述: {product_desc}")
        
        if not product_desc:
            raise HTTPException(status_code=400, detail="产品描述不能为空")

        logger.info("准备调用 DeepSeek API")
        try:
            response = client.chat.completions.create(
                model="deepseek-ai/DeepSeek-V3",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"请为以下产品生成营销文案：{product_desc}"}
                ],
                temperature=0.7,
                max_tokens=1024
            )
            logger.info("DeepSeek API 调用成功")

        except Exception as api_error:
            logger.error(f"调用 DeepSeek API 时发生错误: {str(api_error)}")
            logger.exception(api_error)
            raise HTTPException(
                status_code=500,
                detail=f"AI 接口调用失败: {str(api_error)}"
            )

        generated_text = response.choices[0].message.content
        logger.info(f"生成的原始文本: {generated_text}")

        try:
            parsed_result = parse_generated_text(generated_text)
            logger.info(f"最终解析结果: {parsed_result}")
            return parsed_result
            
        except Exception as parse_error:
            logger.error(f"解析生成的文本时发生错误: {str(parse_error)}")
            logger.exception(parse_error)
            raise HTTPException(
                status_code=500,
                detail=f"解析生成的文本失败: {str(parse_error)}"
            )

    except HTTPException as http_error:
        raise http_error
    except Exception as e:
        logger.error(f"处理请求时发生未预期的错误: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"服务器内部错误: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 