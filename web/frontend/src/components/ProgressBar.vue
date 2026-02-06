<template>
  <div class="progress-container" v-if="visible">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>处理进度</span>
        </div>
      </template>

      <div class="progress-content">
        <el-progress
          :percentage="progress"
          :status="progressStatus"
          :stroke-width="20"
        />
        <div class="progress-text">
          {{ statusText }}
        </div>

        <div v-if="status === 'completed'" class="actions">
          <el-button type="success" @click="handleDownload">
            <el-icon><Download /></el-icon>
            下载结果
          </el-button>
        </div>

        <div v-if="status === 'error'" class="error-message">
          <el-alert
            :title="errorMessage"
            type="error"
            :closable="false"
          />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { createProgressWebSocket, downloadResult } from '@/api/client'

const props = defineProps({
  taskId: String
})

const visible = ref(false)
const progress = ref(0)
const status = ref('pending')
const message = ref('')
const errorMessage = ref('')

let ws = null

const progressStatus = computed(() => {
  if (status.value === 'completed') return 'success'
  if (status.value === 'error') return 'exception'
  return undefined
})

const statusText = computed(() => {
  if (message.value) return message.value
  if (status.value === 'completed') return '处理完成！'
  if (status.value === 'error') return '处理失败'
  if (status.value === 'processing') return `处理中... ${progress.value.toFixed(1)}%`
  return '等待开始...'
})

const connectWebSocket = () => {
  if (!props.taskId) return

  ws = createProgressWebSocket(
    props.taskId,
    (data) => {
      progress.value = data.progress || 0
      status.value = data.status
      message.value = data.message || ''

      if (data.status === 'error') {
        errorMessage.value = data.message || '未知错误'
      }

      if (data.status === 'completed') {
        ElMessage.success('处理完成！')
      }
    },
    (error) => {
      console.error('WebSocket error:', error)
      status.value = 'error'
      errorMessage.value = 'WebSocket 连接错误'
    }
  )
}

const handleDownload = () => {
  downloadResult(props.taskId)
}

watch(() => props.taskId, (newTaskId) => {
  if (newTaskId) {
    visible.value = true
    connectWebSocket()
  }
})

onMounted(() => {
  if (props.taskId) {
    visible.value = true
    connectWebSocket()
  }
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
})
</script>

<style scoped>
.progress-container {
  width: 100%;
  margin-top: 20px;
}

.card-header {
  font-weight: bold;
}

.progress-content {
  padding: 20px 0;
}

.progress-text {
  margin-top: 20px;
  text-align: center;
  font-size: 16px;
  color: #606266;
}

.actions {
  margin-top: 30px;
  text-align: center;
}

.error-message {
  margin-top: 20px;
}
</style>
