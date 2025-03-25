from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from typing import Optional
import httpx
import json
import asyncio
from typing import Dict, Any
import os
from dotenv import load_dotenv
from pydantic import BaseModel

# 加载环境变量
load_dotenv()

app = FastAPI()

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 设置模板目录
templates = Jinja2Templates(directory="templates")

# 存储任务状态的内存字典
tasks: Dict[str, Dict[str, Any]] = {}

class PosterRequest(BaseModel):
    title: str
    sub_title: str
    body_text: str
    prompt_text_zh: str
    wh_ratios: str
    lora_name: str
    api_key: str

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
async def generate_poster(
    title: str = Form(...),
    sub_title: str = Form(...),
    body_text: str = Form(...),
    prompt_text_zh: str = Form(...),
    wh_ratios: str = Form(...),
    lora_name: str = Form(...),
    api_key: str = Form(...)
):
    try:
        # 验证必填字段
        if not all([title, sub_title, body_text, prompt_text_zh, wh_ratios, lora_name, api_key]):
            return JSONResponse(
                status_code=400,
                content={"error": "所有字段都是必填的"}
            )

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
                response = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "X-DashScope-Async": "enable"
                    },
                    json=data,
                    timeout=30.0
                )
                
                response_text = response.text
                print(f"API Response: {response_text}")
                
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
                    "api_key": api_key  # 存储API密钥用于后续查询
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
            response = await client.get(
                f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {task['api_key']}"},
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 