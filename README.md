# AI海报生成器

基于阿里云百炼平台文生图能力的智能海报生成工具，集成硅基流动大模型 DeepSeek-V3 的智能文案生成能力，支持自动生成标题、副标题、正文内容和艺术风格，快速生成精美的营销海报。

## 功能特点

- 🤖 智能文案生成
  - 基于硅基流动 DeepSeek-V3 大模型
  - 一键生成标题、副标题、正文和提示词
  - 智能理解产品特点
  - 自动优化营销文案
- 🎨 支持多种艺术风格选择
  - 2D插画风格
  - 浩瀚星云
  - 中国水墨
  - 剪纸工艺
  - 等多种风格可选
- 📝 灵活的内容定制
  - 自定义标题
  - 自定义副标题
  - 自定义正文内容
  - 自定义提示词
- 📐 支持多种尺寸比例
  - 横版海报
  - 竖版海报
- 🖼️ 图片预览功能
  - 点击图片可查看大图
  - 支持图片放大预览
- ⏱️ 实时生成状态
  - 显示轮询次数
  - 显示生成耗时
  - 实时状态更新

## 示例效果


![示例](static/show1.png)

![示例](static/show2.png)

![示例](static/show3.png)

## 技术栈

- 后端：FastAPI
- 前端：HTML + TailwindCSS
- 文生图：阿里云百炼平台
- 文案生成：硅基流动 DeepSeek-V3 大模型
- 异步处理：httpx

## 部署方式

### 方式一：直接部署

1. 克隆项目
```bash
git clone [项目地址]
cd poster
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
创建 `.env` 文件并添加以下配置：
```bash
SILICONFLOW_API_KEY=你的硅基流动API密钥
DEFAULT_BAILIAN_API_KEY=你的阿里云百炼API密钥
```

4. 运行服务
```bash
python app.py
```

5. 访问应用
打开浏览器访问 `http://localhost:8000`

### 方式二：Docker 部署

1. 确保已安装 Docker 和 Docker Compose

2. 克隆项目
```bash
git clone [项目地址]
cd poster
```

3. 配置环境变量
创建 `.env` 文件并添加以下配置：
```bash
SILICONFLOW_API_KEY=你的硅基流动API密钥
DEFAULT_BAILIAN_API_KEY=你的阿里云百炼API密钥
```

4. 构建并启动容器
```bash
docker-compose up -d
```

5. 访问应用
打开浏览器访问 `http://localhost:8000`

6. 查看容器状态
```bash
docker-compose ps
```

7. 查看容器日志
```bash
docker-compose logs -f
```

8. 停止服务
```bash
docker-compose down
```

## 使用说明

1. 智能生成文案（推荐）
   - 在"AI提示词生成"输入框中输入产品描述
   - 点击"生成提示词"按钮
   - 系统将自动生成标题、副标题、正文和提示词

2. 手动填写内容（可选）
   - 输入标题（最多30字）
   - 输入副标题（最多30字）
   - 输入正文内容（最多50字）
   - 输入提示词（最多50字）

3. 选择海报样式
   - 选择宽高比（横版/竖版）
   - 选择艺术风格

4. 输入阿里云 API Key（可选）
   - 在阿里云控制台获取 API Key
   - 填入 API Key 输入框（不填则使用默认key）

5. 生成海报
   - 点击"生成海报"按钮
   - 等待生成完成
   - 查看生成结果

## 注意事项

- 需要有效的阿里云和硅基流动 API Key
- 生成过程可能需要一定时间，请耐心等待
- 建议使用现代浏览器访问
- Docker 部署时确保 8000 端口未被占用

## 依赖要求

- Python 3.7+
- FastAPI
- uvicorn
- httpx
- jinja2
- python-multipart
- python-dotenv
- openai

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue 或联系开发者。 