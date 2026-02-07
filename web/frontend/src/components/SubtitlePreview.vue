<template>
  <div class="subtitle-preview">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>字幕识别结果</span>
          <el-tag v-if="detectionResult" type="success">
            共 {{ detectionResult.unique_count }} 条字幕
          </el-tag>
        </div>
      </template>

      <div v-if="loading" class="loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <p>正在识别字幕...</p>
        <p class="tip">第一次运行可能需要下载模型，请耐心等待</p>
      </div>

      <div v-else-if="error" class="error-state">
        <el-alert type="error" :closable="false">
          <template #title>
            识别失败
          </template>
          <div>{{ error }}</div>
        </el-alert>
        <div class="error-actions">
          <el-button type="primary" @click="retry">重试</el-button>
          <el-button @click="cancel">返回</el-button>
        </div>
      </div>

      <div v-else-if="detectionResult" class="result-content">
        <el-alert type="info" :closable="false" show-icon>
          <template #title>
            请检查识别结果，可以删除识别错误的字幕
          </template>
        </el-alert>

        <div class="subtitle-stats">
          <el-space wrap>
            <el-statistic title="总帧数" :value="detectionResult.total_frames" />
            <el-statistic title="字幕总数" :value="detectionResult.subtitle_count" />
            <el-statistic title="去重后" :value="detectionResult.unique_count" />
            <el-statistic title="已选择" :value="selectedSubtitles.length" />
          </el-space>
        </div>

        <div class="subtitle-list">
          <el-table
            :data="subtitlesWithSelection"
            stripe
            border
            max-height="500"
            @selection-change="handleSelectionChange"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="text" label="字幕内容" min-width="200">
              <template #default="scope">
                <div class="subtitle-text">{{ scope.row.text }}</div>
              </template>
            </el-table-column>
            <!-- OCR模式：显示帧数 -->
            <el-table-column v-if="!isWhisperMode" prop="frame_count" label="出现帧数" width="100" />
            <el-table-column v-if="!isWhisperMode" label="首次出现" width="100">
              <template #default="scope">
                第 {{ scope.row.frames[0] }} 帧
              </template>
            </el-table-column>
            <el-table-column v-if="!isWhisperMode" label="位置" width="180">
              <template #default="scope">
                <el-tag size="small">
                  Y: {{ scope.row.box[2] }}-{{ scope.row.box[3] }}
                </el-tag>
                <el-tag size="small" class="ml-1">
                  X: {{ scope.row.box[0] }}-{{ scope.row.box[1] }}
                </el-tag>
              </template>
            </el-table-column>

            <!-- Whisper模式：显示时间段 -->
            <el-table-column v-if="isWhisperMode" label="开始时间" width="120">
              <template #default="scope">
                {{ formatTime(scope.row.start) }}
              </template>
            </el-table-column>
            <el-table-column v-if="isWhisperMode" label="结束时间" width="120">
              <template #default="scope">
                {{ formatTime(scope.row.end) }}
              </template>
            </el-table-column>
            <el-table-column v-if="isWhisperMode" label="时长" width="100">
              <template #default="scope">
                {{ (scope.row.end - scope.row.start).toFixed(1) }}s
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="actions">
          <el-button @click="selectAll">全选</el-button>
          <el-button @click="deselectAll">取消全选</el-button>
          <el-button
            type="primary"
            @click="confirmSelection"
            :disabled="selectedSubtitles.length === 0"
          >
            确认并继续 ({{ selectedSubtitles.length }} 条)
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getDetectionResult, confirmDetection } from '@/api/client'

const props = defineProps({
  taskId: String,
  autoLoad: Boolean
})

const emit = defineEmits(['confirmed'])

const loading = ref(false)
const error = ref(null)
const detectionResult = ref(null)
const selectedSubtitles = ref([])

// 是否为 Whisper 模式
const isWhisperMode = computed(() => {
  return detectionResult.value?.method === 'whisper'
})

// 格式化时间（秒 -> MM:SS）
const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// 为字幕添加选中状态
const subtitlesWithSelection = computed(() => {
  if (!detectionResult.value || !detectionResult.value.subtitles) {
    return []
  }
  return detectionResult.value.subtitles.map(sub => ({
    ...sub,
    selected: selectedSubtitles.value.some(s => s.id === sub.id)
  }))
})

// 加载检测结果
const loadDetectionResult = async () => {
  if (!props.taskId) return

  loading.value = true
  error.value = null

  try {
    const result = await getDetectionResult(props.taskId)

    if (result.status === 'detecting') {
      // 还在检测中，轮询
      setTimeout(loadDetectionResult, 2000)
    } else if (result.status === 'completed') {
      detectionResult.value = result
      // 默认全选
      selectedSubtitles.value = result.subtitles
      loading.value = false
    } else if (result.status === 'error') {
      // 检测失败
      error.value = result.message || '检测失败'
      loading.value = false
    }
  } catch (err) {
    if (err.response?.status === 404) {
      error.value = '任务不存在或已过期，请重新上传视频'
    } else {
      error.value = err.response?.data?.detail || err.message || '网络错误，请重试'
    }
    loading.value = false
  }
}

// 重试
const retry = () => {
  error.value = null
  detectionResult.value = null
  loadDetectionResult()
}

// 取消
const cancel = () => {
  error.value = null
  detectionResult.value = null
  emit('cancelled')
}

// 处理选择变化
const handleSelectionChange = (selection) => {
  selectedSubtitles.value = selection
}

// 全选
const selectAll = () => {
  // 触发 table 的全选
  const table = document.querySelector('.el-table')
  if (table) {
    const checkboxes = table.querySelectorAll('.el-checkbox')
    checkboxes.forEach(cb => {
      if (!cb.querySelector('input').checked) {
        cb.click()
      }
    })
  }
}

// 取消全选
const deselectAll = () => {
  selectedSubtitles.value = []
}

// 确认选择
const confirmSelection = async () => {
  if (selectedSubtitles.value.length === 0) {
    ElMessage.warning('请至少选择一条字幕')
    return
  }

  try {
    await confirmDetection(props.taskId, selectedSubtitles.value)
    ElMessage.success('字幕确认成功')
    emit('confirmed', selectedSubtitles.value)
  } catch (err) {
    ElMessage.error('确认失败: ' + (err.response?.data?.detail || err.message))
  }
}

// 监听 taskId 变化
watch(() => props.taskId, (newTaskId) => {
  if (newTaskId && props.autoLoad) {
    loadDetectionResult()
  }
})

// 组件挂载时自动加载
onMounted(() => {
  if (props.taskId && props.autoLoad) {
    loadDetectionResult()
  }
})

// 暴露方法供父组件调用
defineExpose({
  loadDetectionResult
})
</script>

<style scoped>
.subtitle-preview {
  width: 100%;
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

.loading-state,
.error-state {
  padding: 40px;
  text-align: center;
}

.loading-state p {
  margin-top: 10px;
  color: #909399;
}

.loading-state .tip {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
}

.error-actions {
  margin-top: 20px;
}

.error-actions .el-button {
  margin: 0 10px;
}

.result-content {
  padding: 10px 0;
}

.subtitle-stats {
  margin: 20px 0;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 4px;
}

.subtitle-list {
  margin: 20px 0;
}

.subtitle-text {
  word-break: break-all;
  line-height: 1.5;
}

.ml-1 {
  margin-left: 5px;
}

.actions {
  margin-top: 20px;
  text-align: center;
}

.actions .el-button {
  margin: 0 10px;
}
</style>
