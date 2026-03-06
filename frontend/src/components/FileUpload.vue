<template>
  <div class="upload-card">
    <div class="card-header">
      <h2>上传睡眠数据</h2>
      <p class="subtitle">支持标准 EDF 格式文件</p>
    </div>

    <div 
      class="upload-area" 
      :class="{ 'has-file': selectedFile, 'dragging': isDragging }"
      @drop.prevent="handleDrop"
      @dragover.prevent="handleDragOver"
      @dragenter.prevent="handleDragEnter"
      @dragleave.prevent="handleDragLeave"
    >
      <input 
        type="file" 
        @change="handleFileChange" 
        accept=".edf"
        ref="fileInput"
        id="fileInput"
      />
      
      <label for="fileInput" class="upload-zone">
        <svg v-if="!selectedFile" width="64" height="64" viewBox="0 0 64 64" fill="none">
          <path d="M32 16V48M16 32H48" stroke="#667eea" stroke-width="4" stroke-linecap="round"/>
          <rect x="8" y="8" width="48" height="48" rx="8" stroke="#667eea" stroke-width="2" stroke-dasharray="4 4"/>
        </svg>
        
        <div v-if="selectedFile" class="file-info">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <path d="M14 6h20l8 8v28a4 4 0 01-4 4H14a4 4 0 01-4-4V10a4 4 0 014-4z" fill="#667eea" opacity="0.2"/>
            <path d="M34 6v8h8" stroke="#667eea" stroke-width="2"/>
          </svg>
          <p class="file-name">{{ fileName }}</p>
          <p class="file-size">{{ fileSize }}</p>
        </div>
        
        <p v-else class="upload-text">点击或拖拽文件到此处</p>
      </label>
    </div>

    <button 
      @click="uploadFile" 
      :disabled="!selectedFile || loading"
      class="analyze-btn"
    >
      <span v-if="loading" class="loading-spinner"></span>
      {{ loading ? '分析中...' : '开始分析' }}
    </button>
    
    <!-- 加载状态显示 -->
    <div v-if="loading" class="loading-container">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progress + '%' }"></div>
      </div>
      <div class="loading-steps">
        <div class="step" :class="{ active: currentStep >= 1, completed: currentStep > 1 }">
          <div class="step-icon">📁</div>
          <p>读取文件</p>
        </div>
        <div class="step" :class="{ active: currentStep >= 2, completed: currentStep > 2 }">
          <div class="step-icon">🔄</div>
          <p>预处理数据</p>
        </div>
        <div class="step" :class="{ active: currentStep >= 3, completed: currentStep > 3 }">
          <div class="step-icon">🧠</div>
          <p>AI 推理中</p>
        </div>
        <div class="step" :class="{ active: currentStep >= 4, completed: currentStep > 4 }">
          <div class="step-icon">📊</div>
          <p>生成报告</p>
        </div>
      </div>
      <p class="progress-text">{{ loadingMessage }}</p>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-message">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="#f56565" stroke-width="2"/>
        <path d="M12 8v4M12 16h.01" stroke="#f56565" stroke-width="2" stroke-linecap="round"/>
      </svg>
      <p>{{ error }}</p>
      <button @click="error = null" class="close-error">×</button>
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
      loadingMessage: '准备开始...'
    }
  },
  methods: {
    handleDragEnter(e) {
      this.isDragging = true
    },
    
    handleDragOver(e) {
      this.isDragging = true
    },
    
    handleDragLeave(e) {
      // 只有当离开整个拖拽区域时才设置为false
      if (e.target.classList.contains('upload-area')) {
        this.isDragging = false
      }
    },
    
    handleDrop(e) {
      this.isDragging = false
      const files = e.dataTransfer.files
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
      if (!this.selectedFile || this.loading) return
      
      this.loading = true
      this.error = null
      this.currentStep = 0
      this.progress = 0
      
      const formData = new FormData()
      formData.append('file', this.selectedFile)
      
      try {
        // 步骤1: 读取文件
        this.currentStep = 1
        this.progress = 10
        this.loadingMessage = '正在读取文件...'
        await this.delay(300)
        
        // 步骤2: 上传和预处理
        this.currentStep = 2
        this.progress = 30
        this.loadingMessage = '正在预处理数据...'
        
        const token = localStorage.getItem('token');
        if (!token) {
          this.error = '认证失败，请重新登录。';
          this.loading = false;
          return;
        }
        
        // 步骤3: AI推理
        this.currentStep = 3
        this.progress = 60
        this.loadingMessage = 'AI 正在分析睡眠数据...'

        // 调用真实API
        const response = await fetch('http://localhost:8000/api/analyze', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: formData
        })
        
        if (!response.ok) {
          if (response.status === 401) {
            // 清除过期token并通知父组件
            localStorage.removeItem('token');
            this.$emit('authExpired');
            throw new Error('认证已过期，请重新登录。');
          }
          const errorData = await response.json().catch(() => ({ detail: '未知服务器错误' }));
          throw new Error(errorData.detail || `服务器错误: ${response.status}`);
        }
        
        const result = await response.json()
        
        if (result.code !== 200) {
          throw new Error(result.message || '分析失败')
        }
        
        // 步骤4: 生成报告
        this.currentStep = 4
        this.progress = 90
        this.loadingMessage = '正在生成分析报告...'
        await this.delay(500)
        
        this.progress = 100
        this.loadingMessage = '分析完成！'
        
        // 确保数据存在再发送
        if (result.data) {
          console.log('发送分析结果:', result.data)
          this.$emit('analysisComplete', result.data)
        } else {
          throw new Error('API返回数据为空')
        }
        
        // 延迟后重置状态
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
  box-shadow: 0 10px 40px rgba(0,0,0,0.1);
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

.upload-area {
  position: relative;
}

.upload-area input[type="file"] {
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
  border: 3px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  transition: all 0.3s;
}

.step.active .step-icon {
  animation: pulse 1.5s ease-in-out infinite;
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
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
