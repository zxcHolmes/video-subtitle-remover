# Web 版本架构文档

## 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        浏览器客户端                            │
│  ┌───────────────────────────────────────────────────────┐   │
│  │               Vue 3 单页应用 (SPA)                     │   │
│  │                                                        │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │   │
│  │  │ FileUpload   │  │ ConfigPanel  │  │ ProgressBar│  │   │
│  │  │   组件       │  │    组件      │  │    组件    │  │   │
│  │  └──────────────┘  └──────────────┘  └────────────┘  │   │
│  │                                                        │   │
│  │  ┌──────────────────────────────────────────────┐     │   │
│  │  │         API Client (axios + WebSocket)       │     │   │
│  │  └──────────────────────────────────────────────┘     │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          ↕ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI 服务器                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    API 路由层                          │  │
│  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐   │  │
│  │  │Upload│  │Process│ │Status│  │Download│ │  WS  │   │  │
│  │  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘   │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↕                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  业务逻辑层                             │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │           TaskManager (任务管理器)               │  │  │
│  │  │  - 任务队列: Dict[task_id, TaskInfo]            │  │  │
│  │  │  - 服务注册: Dict[task_id, Service]             │  │  │
│  │  │  - 进度跟踪: get_progress()                     │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │                                                         │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │    SubtitleRemovalService (处理服务)            │  │  │
│  │  │  - 包装 SubtitleRemover 类                      │  │  │
│  │  │  - 线程池管理                                   │  │  │
│  │  │  - 实时进度回调                                 │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↕                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            核心算法层 (复用现有代码)                    │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │        SubtitleRemover (backend/main.py)        │  │  │
│  │  │  - SubtitleDetect (检测)                        │  │  │
│  │  │  - STTN Inpaint (填充)                          │  │  │
│  │  │  - LAMA Inpaint (填充)                          │  │  │
│  │  │  - ProPainter Inpaint (填充)                    │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────────┐
│                   文件系统 & 计算资源                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 上传目录      │  │ 输出目录      │  │ 模型目录      │      │
│  │ /tmp/uploads │  │ /tmp/outputs │  │backend/models│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ GPU (CUDA/MPS)│  │   CPU       │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## 数据流图

### 1. 上传流程

```
用户 → [选择文件] → FileUpload 组件
                        ↓
                   FormData 封装
                        ↓
                   POST /api/upload
                        ↓
                  Upload API 路由
                        ↓
                   文件类型验证
                        ↓
                 保存到临时目录
                        ↓
                TaskManager 创建任务
                        ↓
              返回 task_id 给前端
```

### 2. 处理流程

```
用户 → [配置参数] → ConfigPanel 组件
                        ↓
                 POST /api/process
                        ↓
                Process API 路由
                        ↓
           SubtitleRemovalService 创建
                        ↓
                 配置算法参数
                        ↓
              启动独立线程处理
                        ↓
         调用 SubtitleRemover.run()
                        ↓
              [检测] → [填充] → [合成]
                        ↓
                  生成输出文件
```

### 3. 进度监控流程

```
前端建立 WebSocket 连接
        ↓
   WS /ws/{task_id}
        ↓
    while True:
        ↓
   TaskManager.get_progress()
        ↓
   SubtitleService.get_progress()
        ↓
   读取 remover.progress_total
        ↓
   WebSocket.send(progress_data)
        ↓
   等待 0.5 秒
        ↓
   检查是否完成/失败
```

### 4. 下载流程

```
用户 → [点击下载] → ProgressBar 组件
                        ↓
                GET /api/download/{task_id}
                        ↓
               Download API 路由
                        ↓
              验证任务状态 (completed)
                        ↓
              检查输出文件存在性
                        ↓
              FileResponse 流式返回
                        ↓
                 浏览器下载文件
```

## 技术选型理由

### 后端: FastAPI

**选择理由:**
1. **异步支持**: 原生支持 async/await，高并发处理
2. **自动文档**: 自动生成 Swagger/ReDoc API 文档
3. **类型检查**: Pydantic 模型自动验证
4. **WebSocket**: 内置 WebSocket 支持
5. **性能**: 基于 Starlette，性能接近 Node.js

**替代方案对比:**
- Flask: 同步框架，需要额外插件支持 WebSocket
- Django: 过于重量级，不适合 API 项目
- Tornado: 异步但社区支持不如 FastAPI

### 前端: Vue 3 + Element Plus

**选择理由:**
1. **轻量级**: 核心库小于 40KB
2. **响应式**: Composition API 更好的逻辑复用
3. **生态**: Element Plus 提供完整 UI 组件
4. **学习曲线**: 相比 React 更平缓
5. **构建速度**: Vite 极速 HMR

**替代方案对比:**
- React: 更复杂的状态管理
- Angular: 过于重量级
- Svelte: 社区生态较小

### 构建工具: Vite

**选择理由:**
1. **极速**: ESM 原生支持，HMR 毫秒级
2. **简单**: 零配置开箱即用
3. **现代**: 针对 ES2015+ 优化
4. **插件**: 丰富的插件生态

### 通信: WebSocket + REST

**选择理由:**
1. **REST**: 无状态，易于缓存和负载均衡
2. **WebSocket**: 实时双向通信，低延迟
3. **混合使用**: 操作用 REST，通知用 WS

## 核心组件设计

### TaskManager (任务管理器)

**职责:**
- 任务生命周期管理
- 任务状态存储
- 服务注册与查询

**数据结构:**
```python
tasks: Dict[str, TaskInfo] = {
    "uuid-1": TaskInfo(
        task_id="uuid-1",
        status=TaskStatus.PROCESSING,
        progress=45.2,
        file_path="/tmp/uploads/uuid-1/video.mp4",
        output_path=None
    )
}

services: Dict[str, SubtitleRemovalService] = {
    "uuid-1": SubtitleRemovalService(...)
}
```

**优点:**
- 简单高效
- 内存占用小
- 查询速度快 O(1)

**限制:**
- 不持久化，重启丢失
- 单机部署
- 无分布式支持

**改进方向:**
- 集成 Redis 持久化
- 支持任务恢复
- 分布式队列 (Celery)

### SubtitleRemovalService (处理服务)

**职责:**
- 包装 SubtitleRemover 类
- 线程管理
- 进度监听

**关键实现:**
```python
def process(self, video_path, ...):
    # 配置算法
    config.MODE = mode
    config.STTN_SKIP_DETECTION = skip_detection

    # 创建 remover
    self.remover = SubtitleRemover(video_path, ...)

    # 独立线程运行
    self.thread = threading.Thread(target=self._run_remover)
    self.thread.start()

def get_progress(self):
    # 读取 remover.progress_total
    return {
        "status": "processing",
        "progress": self.remover.progress_total,
        ...
    }
```

**优点:**
- 完全复用现有代码
- 无需修改核心算法
- 异步非阻塞

**注意事项:**
- 线程安全
- 资源清理
- 异常捕获

## 性能优化策略

### 后端优化

1. **异步 I/O**
   ```python
   @router.post("/upload")
   async def upload_file(file: UploadFile):
       async with aiofiles.open(path, 'wb') as f:
           await f.write(content)
   ```

2. **线程池**
   - 每个任务独立线程
   - 避免阻塞主进程
   - 资源限制保护

3. **文件流式传输**
   ```python
   return FileResponse(path, media_type="...")
   ```

### 前端优化

1. **代码分割**
   ```javascript
   // Vite 自动代码分割
   const Component = () => import('./Component.vue')
   ```

2. **按需引入**
   ```javascript
   import { ElButton, ElUpload } from 'element-plus'
   ```

3. **WebSocket 优化**
   - 自动重连
   - 心跳检测
   - 错误降级 (轮询)

## 安全策略

### 文件上传安全

1. **类型白名单**
   ```python
   ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', ...}
   ```

2. **大小限制**
   ```python
   MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
   ```

3. **路径遍历防护**
   ```python
   # 使用 UUID 避免路径遍历
   task_id = str(uuid.uuid4())
   ```

### API 安全

1. **CORS 限制**
   ```python
   # 生产环境指定允许的源
   allow_origins=["https://yourdomain.com"]
   ```

2. **速率限制**
   ```python
   # 未来集成 slowapi
   @limiter.limit("10/minute")
   async def upload_file(...):
   ```

3. **认证授权**
   ```python
   # 未来集成 JWT
   from fastapi.security import OAuth2PasswordBearer
   ```

## 可扩展性设计

### 水平扩展

```
Load Balancer (Nginx)
        ↓
┌───────┴───────┐
│               │
Server 1      Server 2
│               │
└───────┬───────┘
        ↓
  Shared Storage (S3/NFS)
  Shared State (Redis)
```

### 任务队列扩展

```python
# 当前: 内存队列
tasks: Dict[str, TaskInfo] = {}

# 未来: Redis 队列
import redis
r = redis.Redis(...)
r.lpush('task_queue', task_id)
```

### 存储扩展

```python
# 当前: 本地文件系统
/tmp/uploads/
/tmp/outputs/

# 未来: 对象存储
s3.upload_file(file_path, bucket, key)
```

## 监控与日志

### 日志策略

```python
import logging

# 结构化日志
logger.info("task_started", extra={
    "task_id": task_id,
    "mode": mode,
    "file_size": file_size
})
```

### 监控指标

1. **系统指标**
   - CPU/内存使用率
   - GPU 使用率
   - 磁盘空间

2. **业务指标**
   - 任务成功率
   - 平均处理时间
   - 并发任务数

3. **性能指标**
   - API 响应时间
   - WebSocket 延迟
   - 吞吐量

### 健康检查

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "tasks": {
            "active": len([t for t in tasks.values() if t.status == "processing"]),
            "total": len(tasks)
        }
    }
```

## 部署最佳实践

### Docker 生产配置

```dockerfile
# 多阶段构建
FROM node:18 AS frontend-builder
WORKDIR /app
COPY web/frontend .
RUN npm ci && npm run build

FROM python:3.9-slim AS runtime
# ... 复制构建产物
```

### Nginx 反向代理

```nginx
upstream fastapi {
    server 127.0.0.1:8000;
}

server {
    listen 80;

    location /api {
        proxy_pass http://fastapi;
    }

    location /ws {
        proxy_pass http://fastapi;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        root /var/www/html;
        try_files $uri $uri/ /index.html;
    }
}
```

### 进程管理

```bash
# 使用 supervisord 或 systemd
[program:vsr-web]
command=/app/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
directory=/app/web/server
autostart=true
autorestart=true
```

## 故障排查指南

### 常见问题

1. **WebSocket 连接失败**
   - 检查防火墙
   - 检查反向代理配置
   - 确认 WebSocket 协议支持

2. **处理卡住**
   - 检查 GPU 内存
   - 查看进程状态
   - 检查模型文件完整性

3. **上传失败**
   - 检查磁盘空间
   - 验证文件权限
   - 查看文件大小限制

### 调试技巧

```python
# 启用调试日志
uvicorn main:app --log-level debug

# 查看任务状态
curl http://localhost:8000/api/status/{task_id}

# 测试 WebSocket
wscat -c ws://localhost:8000/ws/{task_id}
```

## 总结

本架构设计实现了:
- ✅ 完全复用现有核心代码
- ✅ 现代化 Web 界面
- ✅ 实时进度反馈
- ✅ 易于部署和维护
- ✅ 良好的可扩展性

未来可继续优化:
- 任务持久化 (Redis)
- 分布式部署
- 云存储集成
- 性能监控
