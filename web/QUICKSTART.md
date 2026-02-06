# 快速开始 - Web 版本

## 5 分钟快速部署

### 前置要求

- Python 3.8+
- Node.js 16+
- 已安装项目基础依赖（见主 README）

### 步骤 1: 安装 Web 依赖

```bash
# 在项目根目录执行
pip install -r web/requirements-web.txt

cd web/frontend
npm install
cd ../..
```

### 步骤 2: 启动服务

#### 方式 A: 开发模式（推荐用于测试）

```bash
cd web
./start-dev.sh
```

这会启动：
- 后端: http://localhost:8000
- 前端: http://localhost:5173

访问 http://localhost:5173 使用 Web 界面

#### 方式 B: 生产模式

```bash
cd web/frontend
npm run build
cd ../server
uvicorn main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000

### 步骤 3: 使用 Web 界面

1. **上传视频**
   - 拖拽或点击上传按钮
   - 支持 mp4, avi, mov 等格式

2. **配置参数**
   - 选择算法（STTN/LAMA/ProPainter）
   - 是否跳过检测（STTN 模式）
   - 可选：指定字幕区域

3. **开始处理**
   - 点击"开始处理"按钮
   - 实时查看进度

4. **下载结果**
   - 处理完成后点击"下载结果"

## Docker 快速部署

```bash
# 构建镜像
docker build -f docker/Dockerfile.web -t vsr-web .

# 运行容器
docker run -d -p 8000:8000 \
  -v $(pwd)/backend/models:/app/backend/models \
  vsr-web
```

访问 http://localhost:8000

## 常见问题

### Q1: 端口被占用

修改端口：
```bash
# 后端
uvicorn main:app --port 8001

# 前端
vite --port 5174
```

### Q2: 前端构建失败

清除缓存重试：
```bash
cd web/frontend
rm -rf node_modules package-lock.json
npm install
```

### Q3: 无法访问 API

检查 CORS 设置，确保 `web/server/main.py` 中的 CORS 配置正确。

### Q4: WebSocket 连接失败

如果使用反向代理（如 Nginx），需要配置 WebSocket 支持：
```nginx
location /ws {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## 测试 API

运行测试脚本：
```bash
cd web
python test_api.py /path/to/test/video.mp4
```

## 更多文档

- 完整文档: [README-web.md](README-web.md)
- API 文档: http://localhost:8000/docs (启动服务后访问)
- 问题反馈: https://github.com/YaoFANGUK/video-subtitle-remover/issues
