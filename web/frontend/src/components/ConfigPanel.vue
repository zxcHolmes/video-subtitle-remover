<template>
  <div class="config-panel">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>处理配置</span>
        </div>
      </template>

      <el-form :model="config" label-width="120px" label-position="left">
        <!-- 处理模式选择 -->
        <el-form-item label="处理模式">
          <el-radio-group v-model="config.processType">
            <el-radio label="remove">去除字幕</el-radio>
            <el-radio label="translate">翻译字幕</el-radio>
          </el-radio-group>
          <div class="tip">
            <span v-if="config.processType === 'remove'">使用AI算法去除视频中的字幕</span>
            <span v-if="config.processType === 'translate'">识别字幕并翻译，覆盖原字幕</span>
          </div>
        </el-form-item>

        <!-- 去除字幕模式的配置 -->
        <template v-if="config.processType === 'remove'">
          <el-form-item label="处理算法">
            <el-select v-model="config.mode" placeholder="选择算法">
              <el-option label="STTN (真人视频)" value="sttn" />
              <el-option label="LAMA (动画视频)" value="lama" />
              <el-option label="ProPainter (剧烈运动)" value="propainter" />
            </el-select>
            <div class="tip">
              <span v-if="config.mode === 'sttn'">适合真人视频,效果最佳</span>
              <span v-if="config.mode === 'lama'">适合动画视频,速度快</span>
              <span v-if="config.mode === 'propainter'">适合运动剧烈的视频</span>
            </div>
          </el-form-item>

          <el-form-item label="跳过检测" v-if="config.mode === 'sttn'">
            <el-switch v-model="config.skip_detection" />
            <div class="tip">开启后速度更快，但可能误伤无字幕区域</div>
          </el-form-item>
        </template>

        <!-- 翻译字幕模式的配置 -->
        <template v-if="config.processType === 'translate'">
          <el-form-item label="API Key" required>
            <el-input
              v-model="config.apiKey"
              placeholder="请输入 Ollama API Key"
              type="password"
              show-password
            />
            <div class="tip">用于调用大模型翻译字幕</div>
          </el-form-item>

          <el-form-item label="目标语言">
            <el-select v-model="config.targetLang" placeholder="选择目标语言">
              <el-option label="中文" value="中文" />
              <el-option label="English" value="English" />
              <el-option label="日本語" value="日本語" />
              <el-option label="한국어" value="한국어" />
              <el-option label="Español" value="Español" />
              <el-option label="Français" value="Français" />
            </el-select>
          </el-form-item>

          <el-form-item label="字幕底色">
            <el-radio-group v-model="config.bgColor">
              <el-radio label="black">黑色</el-radio>
              <el-radio label="white">白色</el-radio>
            </el-radio-group>
            <div class="tip">用于覆盖原字幕的背景颜色</div>
          </el-form-item>

          <el-form-item label="API 地址">
            <el-input v-model="config.apiBase" placeholder="https://ollama.iamdev.cn" />
            <div class="tip">默认使用官方地址，可自定义</div>
          </el-form-item>

          <el-form-item label="模型">
            <el-input v-model="config.model" placeholder="gpt-oss:20b" />
          </el-form-item>
        </template>

        <!-- 通用配置 -->
        <el-form-item label="字幕区域">
          <el-button @click="showAreaSelector" size="small">
            {{ config.sub_area ? '重新选择区域' : '选择区域（可选）' }}
          </el-button>
          <span v-if="config.sub_area" class="selected-tag">
            已选择: {{ formatArea(config.sub_area) }}
          </span>
          <div class="tip">可选：手动指定字幕区域以提高准确性</div>
        </el-form-item>

        <el-form-item>
          <!-- 去除字幕：一步完成 -->
          <el-button
            v-if="config.processType === 'remove'"
            type="success"
            @click="startProcess"
            :loading="processing"
            :disabled="!taskId"
          >
            {{ processing ? '处理中...' : '开始去除' }}
          </el-button>

          <!-- 翻译字幕：第一步-检测 -->
          <el-button
            v-if="config.processType === 'translate' && !detectionCompleted"
            type="primary"
            @click="startDetection"
            :loading="detecting"
            :disabled="!taskId"
          >
            {{ detecting ? '识别中...' : '开始识别字幕' }}
          </el-button>

          <!-- 翻译字幕：第二步-翻译（需要先确认字幕） -->
          <el-button
            v-if="config.processType === 'translate' && detectionCompleted && subtitlesConfirmed"
            type="success"
            @click="startTranslate"
            :loading="processing"
            :disabled="!config.apiKey"
          >
            {{ processing ? '翻译中...' : '开始翻译' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Area Selector Dialog -->
    <el-dialog v-model="areaDialogVisible" title="选择字幕区域" width="80%">
      <div class="area-info">
        <p>请输入字幕区域坐标 (单位: 像素)</p>
        <p class="tip">格式: [ymin, ymax, xmin, xmax]</p>
        <p class="tip">提示: 字幕通常位于视频底部，例如 1080p 视频的底部 200 像素可设置为 [880, 1080, 0, 1920]</p>
      </div>
      <el-form label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="Y 最小值">
              <el-input-number v-model="areaInput.ymin" :min="0" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Y 最大值">
              <el-input-number v-model="areaInput.ymax" :min="0" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="X 最小值">
              <el-input-number v-model="areaInput.xmin" :min="0" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="X 最大值">
              <el-input-number v-model="areaInput.xmax" :min="0" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="areaDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmArea">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { startProcessing, startTranslation, detectSubtitles } from '@/api/client'

const props = defineProps({
  taskId: String
})

const emit = defineEmits(['process-started', 'detection-started', 'translation-started'])

const config = reactive({
  processType: 'remove',  // 'remove' or 'translate'
  // 去除字幕配置
  mode: 'sttn',
  skip_detection: true,
  // 翻译字幕配置
  apiKey: '',
  apiBase: 'https://ollama.iamdev.cn',
  model: 'gpt-oss:20b',
  targetLang: '中文',
  bgColor: 'black',
  // 通用配置
  sub_area: null
})

const processing = ref(false)
const detecting = ref(false)
const detectionCompleted = ref(false)
const subtitlesConfirmed = ref(false)
const areaDialogVisible = ref(false)
const areaInput = reactive({
  ymin: 0,
  ymax: 100,
  xmin: 0,
  xmax: 100
})

const showAreaSelector = () => {
  areaDialogVisible.value = true
}

const confirmArea = () => {
  config.sub_area = [
    areaInput.ymin,
    areaInput.ymax,
    areaInput.xmin,
    areaInput.xmax
  ]
  areaDialogVisible.value = false
  ElMessage.success('区域已设置')
}

const formatArea = (area) => {
  if (!area) return ''
  return `[${area.join(', ')}]`
}

// 去除字幕（一步完成）
const startProcess = async () => {
  if (!props.taskId) {
    ElMessage.warning('请先上传文件')
    return
  }

  processing.value = true
  try {
    const result = await startProcessing(props.taskId, config)
    ElMessage.success('开始去除字幕')
    emit('process-started', result)
  } catch (error) {
    ElMessage.error('启动失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    processing.value = false
  }
}

// 翻译字幕 - 阶段1：检测字幕
const startDetection = async () => {
  if (!props.taskId) {
    ElMessage.warning('请先上传文件')
    return
  }

  detecting.value = true
  try {
    const result = await detectSubtitles(props.taskId, config.sub_area)
    ElMessage.success('开始识别字幕')
    detectionCompleted.value = true
    emit('detection-started', result)
  } catch (error) {
    ElMessage.error('识别失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    detecting.value = false
  }
}

// 翻译字幕 - 阶段2：翻译已确认的字幕
const startTranslate = async () => {
  if (!props.taskId) {
    ElMessage.warning('请先上传文件')
    return
  }

  if (!config.apiKey) {
    ElMessage.warning('请输入 API Key')
    return
  }

  if (!subtitlesConfirmed.value) {
    ElMessage.warning('请先确认字幕识别结果')
    return
  }

  processing.value = true
  try {
    const result = await startTranslation(props.taskId, config)
    ElMessage.success('开始翻译字幕')
    emit('translation-started', result)
  } catch (error) {
    ElMessage.error('翻译失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    processing.value = false
  }
}

// 处理字幕确认
const handleSubtitlesConfirmed = () => {
  subtitlesConfirmed.value = true
}

// 暴露方法供父组件使用
defineExpose({
  handleSubtitlesConfirmed
})
</script>

<style scoped>
.config-panel {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

.tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.selected-tag {
  margin-left: 10px;
  color: #67c23a;
  font-size: 14px;
}

.area-info {
  margin-bottom: 20px;
}

.area-info p {
  margin: 5px 0;
}
</style>
