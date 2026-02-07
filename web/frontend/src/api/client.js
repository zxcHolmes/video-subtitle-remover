import axios from 'axios'

const API_BASE = '/api'

/**
 * Upload video file
 */
export const uploadVideo = async (file) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await axios.post(`${API_BASE}/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })

  return response.data
}

/**
 * Start processing
 */
export const startProcessing = async (taskId, config) => {
  const response = await axios.post(`${API_BASE}/process`, {
    task_id: taskId,
    mode: config.mode,
    sub_area: config.sub_area,
    skip_detection: config.skip_detection
  })

  return response.data
}

/**
 * Get task status
 */
export const getStatus = async (taskId) => {
  const response = await axios.get(`${API_BASE}/status/${taskId}`)
  return response.data
}

/**
 * Detect subtitles (Stage 1)
 */
export const detectSubtitles = async (taskId, subArea) => {
  const response = await axios.post(`${API_BASE}/detect`, {
    task_id: taskId,
    sub_area: subArea
  })
  return response.data
}

/**
 * Get detection result
 */
export const getDetectionResult = async (taskId) => {
  const response = await axios.get(`${API_BASE}/detect/${taskId}`)
  return response.data
}

/**
 * Confirm detected subtitles
 */
export const confirmDetection = async (taskId, confirmedSubtitles) => {
  const response = await axios.post(`${API_BASE}/detect/confirm`, {
    task_id: taskId,
    confirmed_subtitles: confirmedSubtitles
  })
  return response.data
}

/**
 * Start translation (Stage 2)
 */
export const startTranslation = async (taskId, config) => {
  const response = await axios.post(`${API_BASE}/translate`, {
    task_id: taskId,
    api_key: config.apiKey,
    api_base: config.apiBase || 'https://ollama.iamdev.cn',
    model: config.model || 'gpt-oss:20b',
    target_lang: config.targetLang || '中文',
    bg_color: config.bgColor || 'black',
    sub_area: config.sub_area
  })

  return response.data
}

/**
 * Download result
 */
export const downloadResult = (taskId) => {
  window.location.href = `${API_BASE}/download/${taskId}`
}

/**
 * Create WebSocket connection for progress updates
 */
export const createProgressWebSocket = (taskId, onMessage, onError) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${taskId}`)

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    onMessage(data)
  }

  ws.onerror = (error) => {
    if (onError) onError(error)
  }

  return ws
}
