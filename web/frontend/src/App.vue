<template>
  <div id="app">
    <el-container>
      <el-header>
        <div class="header-content">
          <h1>视频字幕去除器</h1>
          <p class="subtitle">Video Subtitle Remover - Web Version</p>
        </div>
      </el-header>

      <el-main>
        <el-row :gutter="20" justify="center">
          <el-col :xs="24" :sm="20" :md="16" :lg="14" :xl="12">
            <div class="main-content">
              <!-- Step 1: Upload -->
              <el-steps :active="currentStep" finish-status="success" align-center>
                <el-step title="上传文件" />
                <el-step title="配置参数" />
                <el-step title="处理视频" />
                <el-step title="下载结果" />
              </el-steps>

              <div class="step-content">
                <!-- Upload Component -->
                <div v-show="currentStep === 0">
                  <FileUpload @upload-success="handleUploadSuccess" />
                </div>

                <!-- Config Component -->
                <div v-show="currentStep >= 1">
                  <ConfigPanel
                    :task-id="taskId"
                    @process-started="handleProcessStarted"
                  />
                </div>

                <!-- Progress Component -->
                <div v-show="currentStep >= 2">
                  <ProgressBar :task-id="taskId" />
                </div>
              </div>

              <!-- Info Panel -->
              <el-card class="info-panel" shadow="never">
                <template #header>
                  <span>使用说明</span>
                </template>
                <el-collapse>
                  <el-collapse-item title="算法选择指南" name="1">
                    <ul>
                      <li><strong>STTN:</strong> 适合真人视频，效果最佳，处理速度适中</li>
                      <li><strong>LAMA:</strong> 适合动画视频，速度快，占用显存少</li>
                      <li><strong>ProPainter:</strong> 适合运动剧烈的视频，效果好但速度慢</li>
                    </ul>
                  </el-collapse-item>
                  <el-collapse-item title="注意事项" name="2">
                    <ul>
                      <li>首次运行会自动下载模型文件，请耐心等待</li>
                      <li>处理时间取决于视频长度和分辨率</li>
                      <li>建议先用短视频测试效果</li>
                      <li>跳过检测模式速度更快，但可能误伤无字幕区域</li>
                    </ul>
                  </el-collapse-item>
                  <el-collapse-item title="字幕区域说明" name="3">
                    <p>如果默认检测不准确，可以手动指定字幕区域坐标：</p>
                    <ul>
                      <li>坐标格式: [ymin, ymax, xmin, xmax]</li>
                      <li>单位为像素，原点在左上角</li>
                      <li>示例: [800, 1000, 0, 1920] 表示底部 200 像素高度的区域</li>
                    </ul>
                  </el-collapse-item>
                </el-collapse>
              </el-card>
            </div>
          </el-col>
        </el-row>
      </el-main>

      <el-footer>
        <div class="footer-content">
          <p>
            Powered by
            <a href="https://github.com/YaoFANGUK/video-subtitle-remover" target="_blank">
              video-subtitle-remover
            </a>
          </p>
        </div>
      </el-footer>
    </el-container>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import FileUpload from './components/FileUpload.vue'
import ConfigPanel from './components/ConfigPanel.vue'
import ProgressBar from './components/ProgressBar.vue'

const currentStep = ref(0)
const taskId = ref('')

const handleUploadSuccess = (result) => {
  taskId.value = result.task_id
  currentStep.value = 1
}

const handleProcessStarted = () => {
  currentStep.value = 2
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
}

#app {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.el-container {
  min-height: 100vh;
}

.el-header {
  background: transparent;
  padding: 40px 20px;
}

.header-content {
  text-align: center;
  color: white;
}

.header-content h1 {
  font-size: 36px;
  margin-bottom: 10px;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
}

.header-content .subtitle {
  font-size: 16px;
  opacity: 0.9;
}

.el-main {
  padding: 20px;
}

.main-content {
  background: white;
  border-radius: 10px;
  padding: 30px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.step-content {
  margin-top: 40px;
}

.info-panel {
  margin-top: 30px;
}

.info-panel ul {
  padding-left: 20px;
}

.info-panel li {
  margin: 10px 0;
  line-height: 1.6;
}

.el-footer {
  background: transparent;
  color: white;
  text-align: center;
  padding: 20px;
}

.footer-content a {
  color: white;
  text-decoration: none;
  border-bottom: 1px solid white;
}

.footer-content a:hover {
  opacity: 0.8;
}
</style>
