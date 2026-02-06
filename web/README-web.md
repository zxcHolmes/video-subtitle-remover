# Video Subtitle Remover - Web Version

基于 FastAPI + Vue 3 的视频字幕去除器 Web 版本，提供友好的浏览器界面。

## 功能特性

- ✅ 文件拖拽上传
- ✅ 三种处理算法选择（STTN/LAMA/ProPainter）
- ✅ 实时进度显示（WebSocket）
- ✅ 自定义字幕区域
- ✅ 一键下载结果
- ✅ 响应式设计，支持移动端

## 技术栈

**后端:**
- FastAPI 0.104.1
- Python 3.8+
- WebSocket 实时通信

**前端:**
- Vue 3.3+
- Element Plus 2.4+
- Vite 5.0+

## 快速开始

### 1. 安装依赖

#### 后端依赖
```bash
# 安装基础依赖（如果还没安装）
pip install -r requirements.txt

# 安装 Web 专用依赖
pip install -r web/requirements-web.txt
```

#### 前端依赖
```bash
cd web/frontend
npm install
```

### 2. 启动服务

#### 开发模式

**启动后端服务:**
```bash
cd web/server
python main.py
# 或使用 uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**启动前端开发服务器:**
```bash
cd web/frontend
npm run dev
```

访问: http://localhost:5173

#### 生产模式

**构建前端:**
```bash
cd web/frontend
npm run build
```

**启动服务:**
```bash
cd web/server
uvicorn main:app --host 0.0.0.0 --port 8000
```

访问: http://localhost:8000

## API 文档

启动后端服务后，访问以下地址查看自动生成的 API 文档:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 使用说明

### 1. 上传视频
- 支持拖拽上传或点击选择
- 支持的格式: mp4, avi, mov, mkv, jpg, png 等

### 2. 配置参数

**算法选择:**
- **STTN**: 适合真人视频，效果最佳
- **LAMA**: 适合动画视频，速度快
- **ProPainter**: 适合运动剧烈的视频

**跳过检测 (仅 STTN):**
- 开启: 速度更快，但可能误伤无字幕区域
- 关闭: 更准确，但速度较慢

**字幕区域 (可选):**
- 手动指定字幕区域坐标
- 格式: [ymin, ymax, xmin, xmax]
- 示例: [800, 1000, 0, 1920] (1080p 视频底部 200px)

### 3. 处理视频
- 点击"开始处理"按钮
- 实时查看处理进度
- 自动下载或手动下载结果

## 配置说明

### 环境变量

可以通过环境变量配置服务:

```bash
# 后端端口
export PORT=8000

# 上传文件存储路径
export UPLOAD_DIR=/tmp/subtitle-remover/uploads

# 输出文件存储路径
export OUTPUT_DIR=/tmp/subtitle-remover/outputs
```

### 模型文件

首次运行会自动下载模型文件到 `backend/models/` 目录:
- STTN 模型: ~200MB
- LAMA 模型: ~50MB
- ProPainter 模型: ~100MB

## Docker 部署

### 构建镜像
```bash
docker build -f docker/Dockerfile.web -t video-subtitle-remover-web .
```

### 运行容器
```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/backend/models:/app/backend/models \
  --name subtitle-remover \
  video-subtitle-remover-web
```

访问: http://localhost:8000

## 性能优化

### GPU 加速
- 自动检测 CUDA/MPS 设备
- 配置文件: `backend/config.py`

### 并发处理
- 支持多任务队列
- 每个任务独立线程处理

### 存储优化
- 定期清理临时文件
- 可配置文件保留时长

## 常见问题

### 1. 上传失败
- 检查文件格式是否支持
- 检查文件大小限制
- 查看后端日志

### 2. 处理超时
- 长视频可能需要较长时间
- 检查 GPU/CPU 资源
- 调整超时配置

### 3. 显存不足
- 切换到 LAMA 算法（占用更少）
- 降低视频分辨率
- 使用 CPU 模式

### 4. WebSocket 连接失败
- 检查防火墙设置
- 检查反向代理配置（Nginx/Apache）
- 确认 WebSocket 支持

## 开发指南

### 项目结构
```
web/
├── server/               # FastAPI 后端
│   ├── main.py          # 入口文件
│   ├── api/             # API 路由
│   ├── services/        # 业务逻辑
│   ├── models/          # 数据模型
│   └── utils/           # 工具函数
├── frontend/            # Vue 3 前端
│   ├── src/
│   │   ├── App.vue      # 主组件
│   │   ├── components/  # 子组件
│   │   └── api/         # API 客户端
│   └── package.json
└── requirements-web.txt # Web 依赖
```

### 添加新功能

1. **后端 API:**
   - 在 `server/api/` 添加路由
   - 在 `server/services/` 实现业务逻辑

2. **前端组件:**
   - 在 `frontend/src/components/` 添加 Vue 组件
   - 在 `frontend/src/api/client.js` 添加 API 调用

### 测试

**后端测试:**
```bash
pytest tests/test_web_api.py
```

**前端测试:**
```bash
cd web/frontend
npm run test
```

## 路线图

- [ ] 批量处理多个视频
- [ ] 视频预览功能
- [ ] 处理历史记录
- [ ] 用户认证系统
- [ ] 云存储支持（S3/OSS）
- [ ] 视频压缩选项
- [ ] 自定义水印去除

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

与主项目保持一致

## 支持

- 项目主页: https://github.com/YaoFANGUK/video-subtitle-remover
- 问题反馈: https://github.com/YaoFANGUK/video-subtitle-remover/issues
