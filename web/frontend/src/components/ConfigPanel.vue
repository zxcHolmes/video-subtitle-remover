<template>
  <div class="config-panel">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>处理配置</span>
        </div>
      </template>

      <el-form :model="config" label-width="120px" label-position="left">
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
          <el-button
            type="success"
            @click="startProcess"
            :loading="processing"
            :disabled="!taskId"
          >
            {{ processing ? '处理中...' : '开始处理' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Area Selector Dialog -->
    <el-dialog v-model="areaDialogVisible" title="选择字幕区域" width="80%">
      <div class="area-info">
        <p>请输入字幕区域坐标 (单位: 像素)</p>
        <p class="tip">格式: [ymin, ymax, xmin, xmax]</p>
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
import { startProcessing } from '@/api/client'

const props = defineProps({
  taskId: String
})

const emit = defineEmits(['process-started'])

const config = reactive({
  mode: 'sttn',
  skip_detection: true,
  sub_area: null
})

const processing = ref(false)
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

const startProcess = async () => {
  if (!props.taskId) {
    ElMessage.warning('请先上传文件')
    return
  }

  processing.value = true
  try {
    const result = await startProcessing(props.taskId, config)
    ElMessage.success('开始处理')
    emit('process-started', result)
  } catch (error) {
    ElMessage.error('启动失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    processing.value = false
  }
}
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
