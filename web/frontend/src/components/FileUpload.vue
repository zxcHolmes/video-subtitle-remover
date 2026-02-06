<template>
  <div class="upload-container">
    <el-upload
      ref="uploadRef"
      drag
      :auto-upload="false"
      :on-change="handleFileChange"
      :limit="1"
      accept="video/*,image/*"
      class="upload-demo"
    >
      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
      <div class="el-upload__text">
        拖拽文件到此处或<em>点击上传</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">
          支持视频和图片格式 (mp4, avi, mov, jpg, png 等)
        </div>
      </template>
    </el-upload>

    <div class="upload-actions">
      <el-button
        type="primary"
        @click="uploadFile"
        :loading="uploading"
        :disabled="!file"
      >
        {{ uploading ? '上传中...' : '上传文件' }}
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { uploadVideo } from '@/api/client'

const emit = defineEmits(['upload-success'])

const uploadRef = ref(null)
const file = ref(null)
const uploading = ref(false)

const handleFileChange = (uploadFile) => {
  file.value = uploadFile.raw
}

const uploadFile = async () => {
  if (!file.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  uploading.value = true
  try {
    const result = await uploadVideo(file.value)
    ElMessage.success('上传成功')
    emit('upload-success', result)
  } catch (error) {
    ElMessage.error('上传失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.upload-container {
  width: 100%;
}

.upload-demo {
  width: 100%;
}

.upload-actions {
  margin-top: 20px;
  text-align: center;
}
</style>
