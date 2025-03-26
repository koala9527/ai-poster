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
SYSTEM_PROMPT = """你是一个专业的营销文案生成助手。请根据用户提供的产品描述，生成以下四个要素，并严格遵守字数限制：

1. 标题：简短有力，突出产品核心价值（最多30字）
2. 副标题：补充说明产品主要特点（最多30字）
3. 正文：详细描述产品优势，使用数据支撑（最多50字）
4. 提示词：用于AI绘画的关键词，包含产品特征、风格、场景等（最多50字）

请以JSON格式返回，格式如下：
{
    "title": "标题(限30字)",
    "sub_title": "副标题(限30字)",
    "body_text": "正文(限50字)",
    "prompt_text_zh": "提示词(限50字)"
}

注意：请严格控制每个字段的字数，超出部分会被截断。"""

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

@app.post("/generate_prompt")
async def generate_prompt(request: Request):
    try:
        data = await request.json()
        product_desc = data.get("product_desc")
        
        if not product_desc:
            raise HTTPException(status_code=400, detail="产品描述不能为空")

        # 调用硅基流动API
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"请为以下产品生成营销文案：{product_desc}"}
            ],
            temperature=0.7,
            max_tokens=1024
        )

        # 获取生成的文本
        generated_text = response.choices[0].message.content
        
        # 尝试解析JSON
        try:
            result = json.loads(generated_text)
        except json.JSONDecodeError:
            # 如果无法直接解析JSON，尝试提取JSON部分
            json_match = re.search(r'\{.*\}', generated_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise HTTPException(status_code=500, detail="无法解析AI生成的文本")

        # 验证返回的JSON格式并限制字数
        required_fields = ["title", "sub_title", "body_text", "prompt_text_zh"]
        for field in required_fields:
            if field not in result:
                raise HTTPException(status_code=500, detail=f"AI生成的内容缺少必要字段：{field}")
            
        # 截断超出长度的文本
        result["title"] = result["title"][:30]
        result["sub_title"] = result["sub_title"][:30]
        result["body_text"] = result["body_text"][:50]
        result["prompt_text_zh"] = result["prompt_text_zh"][:50]

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 