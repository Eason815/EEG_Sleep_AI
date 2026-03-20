<template>
  <div class="upload-card">
    <div class="card-header">
      <h2>上传睡眠数据</h2>
      <p class="subtitle">支持标准 EDF 格式文件，并可切换不同模型进行推理</p>
    </div>

    <div class="model-section">
      <label class="model-label" for="modelSelect">选择模型</label>
      <select
        id="modelSelect"
        v-model="selectedModelId"
        class="model-select"
        :disabled="modelsLoading || !models.length || loading"
      >
        <option v-for="model in models" :key="model.id" :value="model.id">
          {{ model.name }}
        </option>
      </select>
      <p v-if="selectedModel" class="model-hint">
        当前模型：{{ selectedModel.family_label }} / {{ selectedModel.name }}
      </p>
      <p v-else-if="modelsLoading" class="model-hint">正在加载模型列表...</p>
      <p v-else-if="!models.length" class="model-hint error-text">
        当前没有可用模型，请先将 `.pth` 文件放入后端 `data` 子目录。
      </p>
    </div>

    <div
      class="upload-area"
      :class="{ 'has-file': selectedFile, dragging: isDragging }"
      @drop.prevent="handleDrop"
      @dragover.prevent="handleDragOver"
      @dragenter.prevent="handleDragEnter"
      @dragleave.prevent="handleDragLeave"
    >
      <input
        id="fileInput"
        ref="fileInput"
        type="file"
        accept=".edf"
        @change="handleFileChange"
      />

      <label for="fileInput" class="upload-zone">
        <svg v-if="!selectedFile" width="64" height="64" viewBox="0 0 64 64" fill="none">
          <path d="M32 16V48M16 32H48" stroke="#667eea" stroke-width="4" stroke-linecap="round" />
          <rect x="8" y="8" width="48" height="48" rx="8" stroke="#667eea" stroke-width="2" stroke-dasharray="4 4" />
        </svg>

        <div v-if="selectedFile" class="file-info">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <path d="M14 6h20l8 8v28a4 4 0 01-4 4H14a4 4 0 01-4-4V10a4 4 0 014-4z" fill="#667eea" opacity="0.2" />
            <path d="M34 6v8h8" stroke="#667eea" stroke-width="2" />
          </svg>
          <p class="file-name">{{ fileName }}</p>
          <p class="file-size">{{ fileSize }}</p>
        </div>

        <p v-else class="upload-text">点击或拖拽文件到此处</p>
      </label>
    </div>

    <button
      class="analyze-btn"
      :disabled="!selectedFile || loading || !selectedModelId || !models.length"
      @click="uploadFile"
    >
      <span v-if="loading" class="loading-spinner"></span>
      {{ loading ? '分析中...' : '开始分析' }}
    </button>

    <div v-if="loading" class="loading-container">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progress + '%' }"></div>
      </div>
      <div class="loading-steps">
        <div class="step" :class="{ active: currentStep >= 1, completed: currentStep > 1 }">
          <div class="step-icon">📄</div>
          <p>读取文件</p>
        </div>
        <div class="step" :class="{ active: currentStep >= 2, completed: currentStep > 2 }">
          <div class="step-icon">🔬</div>
          <p>预处理</p>
        </div>
        <div class="step" :class="{ active: currentStep >= 3, completed: currentStep > 3 }">
          <div class="step-icon">🧠</div>
          <p>模型推理</p>
        </div>
        <div class="step" :class="{ active: currentStep >= 4, completed: currentStep > 4 }">
          <div class="step-icon">📊</div>
          <p>生成报告</p>
        </div>
      </div>
      <p class="progress-text">{{ loadingMessage }}</p>
    </div>

    <div v-if="error" class="error-message">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="#f56565" stroke-width="2" />
        <path d="M12 8v4M12 16h.01" stroke="#f56565" stroke-width="2" stroke-linecap="round" />
      </svg>
      <p>{{ error }}</p>
      <button class="close-error" @click="error = null">×</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FileUpload',
  data() {
    return {
      selectedFile: null,
      fileName: '',
      fileSize: '',
      loading: false,
      isDragging: false,
      error: null,
      currentStep: 0,
      progress: 0,
      loadingMessage: '准备开始...',
      models: [],
      selectedModelId: '',
      modelsLoading: false
    }
  },
  computed: {
    selectedModel() {
      return this.models.find(model => model.id === this.selectedModelId) || null
    }
  },
  mounted() {
    this.fetchModels()
  },
  methods: {
    async fetchModels() {
      this.modelsLoading = true
      this.error = null

      try {
        const response = await fetch('http://localhost:8000/api/models')
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: '加载模型列表失败' }))
          throw new Error(errorData.detail || '加载模型列表失败')
        }

        const data = await response.json()
        this.models = data.models || []
        this.selectedModelId = data.default_model_id || (this.models[0] && this.models[0].id) || ''
      } catch (error) {
        console.error('加载模型列表失败:', error)
        this.error = error.message || '加载模型列表失败'
      } finally {
        this.modelsLoading = false
      }
    },
    handleDragEnter() {
      this.isDragging = true
    },
    handleDragOver() {
      this.isDragging = true
    },
    handleDragLeave(event) {
      if (event.target.classList.contains('upload-area')) {
        this.isDragging = false
      }
    },
    handleDrop(event) {
      this.isDragging = false
      const files = event.dataTransfer.files
      if (files.length > 0) {
        const file = files[0]
        if (file.name.endsWith('.edf')) {
          this.selectedFile = file
          this.fileName = file.name
          this.fileSize = this.formatFileSize(file.size)
          this.error = null
        } else {
          this.error = '请上传 .edf 格式的文件'
        }
      }
    },
    handleFileChange(event) {
      const file = event.target.files[0]
      if (file) {
        this.selectedFile = file
        this.fileName = file.name
        this.fileSize = this.formatFileSize(file.size)
        this.error = null
      }
    },
    formatFileSize(bytes) {
      if (bytes < 1024) return bytes + ' B'
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
      return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
    },
    async uploadFile() {
      if (!this.selectedFile || this.loading || !this.selectedModelId) return

      this.loading = true
      this.error = null
      this.currentStep = 0
      this.progress = 0

      const formData = new FormData()
      formData.append('file', this.selectedFile)
      formData.append('model_id', this.selectedModelId)

      try {
        this.currentStep = 1
        this.progress = 10
        this.loadingMessage = '正在读取文件...'
        await this.delay(300)

        this.currentStep = 2
        this.progress = 30
        this.loadingMessage = '正在预处理数据...'

        const token = localStorage.getItem('token')
        if (!token) {
          this.error = '认证失败，请重新登录。'
          this.loading = false
          return
        }

        this.currentStep = 3
        this.progress = 60
        this.loadingMessage = `正在使用 ${this.selectedModel ? this.selectedModel.name : '所选模型'} 进行推理...`

        const response = await fetch('http://localhost:8000/api/analyze', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`
          },
          body: formData
        })

        if (!response.ok) {
          if (response.status === 401) {
            localStorage.removeItem('token')
            this.$emit('authExpired')
            throw new Error('认证已过期，请重新登录。')
          }
          const errorData = await response.json().catch(() => ({ detail: '未知服务器错误' }))
          throw new Error(errorData.detail || `服务器错误: ${response.status}`)
        }

        const result = await response.json()
        if (result.code !== 200) {
          throw new Error(result.message || '分析失败')
        }

        this.currentStep = 4
        this.progress = 90
        this.loadingMessage = '正在生成分析报告...'
        await this.delay(500)

        this.progress = 100
        this.loadingMessage = '分析完成'

        if (result.data) {
          this.$emit('analysisComplete', result.data)
        } else {
          throw new Error('API 返回数据为空')
        }

        await this.delay(500)
      } catch (error) {
        console.error('分析失败:', error)
        this.error = error.message || '分析失败，请检查网络连接和后端服务'
        this.currentStep = 0
      } finally {
        this.loading = false
        this.progress = 0
      }
    },
    delay(ms) {
      return new Promise(resolve => setTimeout(resolve, ms))
    }
  }
}
</script>

<style scoped>
.upload-card {
  background: white;
  border-radius: 20px;
  padding: 2.5rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.card-header {
  text-align: center;
  margin-bottom: 2rem;
}

.card-header h2 {
  font-size: 2rem;
  color: #333;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: #666;
  font-size: 0.95rem;
}

.model-section {
  margin-bottom: 1.5rem;
}

.model-label {
  display: block;
  font-size: 0.95rem;
  font-weight: 600;
  color: #444;
  margin-bottom: 0.5rem;
}

.model-select {
  width: 100%;
  padding: 0.85rem 1rem;
  border: 2px solid #d9e2f2;
  border-radius: 12px;
  font-size: 1rem;
  color: #333;
  background: #f8faff;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.model-select:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.15);
}

.model-hint {
  margin-top: 0.6rem;
  color: #667;
  font-size: 0.9rem;
}

.error-text {
  color: #c53030;
}

.upload-area {
  position: relative;
}

.upload-area input[type='file'] {
  display: none;
}

.upload-zone {
  display: block;
  padding: 3rem;
  border: 3px dashed #ddd;
  border-radius: 15px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #fafafa;
}

.upload-zone:hover {
  border-color: #667eea;
  background: #f0f4ff;
}

.dragging .upload-zone {
  border-color: #667eea;
  background: #f0f4ff;
  transform: scale(1.02);
}

.has-file .upload-zone {
  border-color: #48bb78;
  background: #f0fff4;
}

.file-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.file-name {
  font-weight: 600;
  color: #333;
  font-size: 1.1rem;
}

.file-size {
  color: #666;
  font-size: 0.9rem;
}

.upload-text {
  color: #666;
  font-size: 1rem;
  margin-top: 1rem;
}

.analyze-btn {
  width: 100%;
  padding: 1rem;
  margin-top: 1.5rem;
  font-size: 1.1rem;
  font-weight: 600;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.analyze-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
}

.analyze-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-container {
  margin-top: 2rem;
  padding: 1.5rem;
  background: #f8f9ff;
  border-radius: 15px;
}

.progress-bar {
  height: 8px;
  background: #e0e0e0;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 1.5rem;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.3s ease;
  border-radius: 10px;
}

.loading-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1rem;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  opacity: 0.3;
  transition: all 0.3s;
}

.step.active {
  opacity: 1;
}

.step.completed {
  opacity: 0.7;
}

.step-icon {
  font-size: 2rem;
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border-radius: 50%;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
}

.step.active .step-icon {
  animation: pulse 1.5s ease-in-out infinite;
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
}

.step p {
  font-size: 0.85rem;
  color: #666;
  font-weight: 500;
}

.progress-text {
  text-align: center;
  color: #667eea;
  font-size: 0.95rem;
  font-weight: 600;
}

.error-message {
  margin-top: 1rem;
  padding: 1rem;
  background: #fff5f5;
  border: 1px solid #feb2b2;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: #c53030;
  position: relative;
}

.error-message p {
  flex: 1;
  font-size: 0.95rem;
}

.close-error {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #c53030;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background 0.2s;
}

.close-error:hover {
  background: rgba(197, 48, 48, 0.1);
}

@media (max-width: 768px) {
  .loading-steps {
    grid-template-columns: repeat(2, 1fr);
  }

  .step-icon {
    width: 50px;
    height: 50px;
    font-size: 1.5rem;
  }
}
</style>
