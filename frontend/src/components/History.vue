<template>
  <div class="history-container">
    <div class="history-header">
      <h2>📋 历史记录</h2>
      <button @click="fetchHistory" class="refresh-btn" :disabled="loading">
        <span v-if="loading" class="loading-spinner"></span>
        <span v-else>🔄 刷新</span>
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading && records.length === 0" class="loading-state">
      <div class="loading-icon">⏳</div>
      <p>加载中...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading && records.length === 0" class="empty-state">
      <div class="empty-icon">📭</div>
      <h3>暂无历史记录</h3>
      <p>开始您的第一次睡眠分析吧！</p>
    </div>

    <!-- 记录列表 -->
    <div v-else class="records-list">
      <div 
        v-for="record in records" 
        :key="record.id" 
        class="record-card"
      >
        <div class="record-icon">
          <span>📊</span>
        </div>
        <div class="record-info" @click="viewRecord(record)">
          <h4 class="record-filename">{{ record.filename }}</h4>
          <p class="record-time">{{ formatTime(record.created_at) }}</p>
        </div>
        <div class="record-stats" @click="viewRecord(record)">
          <div class="stat-item">
            <span class="stat-label">质量评分</span>
            <span class="stat-value" :class="getScoreClass(record.quality_score)">
              {{ record.quality_score || '-' }}
            </span>
          </div>
          <div class="stat-item">
            <span class="stat-label">时长</span>
            <span class="stat-value">{{ record.duration_hours ? record.duration_hours.toFixed(1) + 'h' : '-' }}</span>
          </div>
        </div>
        <button class="delete-btn" @click.stop="confirmDelete(record)" title="删除记录">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M6 6l8 8M14 6l-8 8" stroke="#e53e3e" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </button>
        <div class="record-arrow" @click="viewRecord(record)">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M9 18l6-6-6-6" stroke="#667eea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-message">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="9" stroke="#f56565" stroke-width="2"/>
        <path d="M10 6v4M10 14h.01" stroke="#f56565" stroke-width="2" stroke-linecap="round"/>
      </svg>
      <p>{{ error }}</p>
      <button @click="error = null" class="close-error">×</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'History',
  data() {
    return {
      records: [],
      loading: false,
      error: null
    }
  },
  mounted() {
    this.fetchHistory()
  },
  methods: {
    async fetchHistory() {
      this.loading = true
      this.error = null
      
      const token = localStorage.getItem('token')
      if (!token) {
        this.error = '请先登录'
        this.loading = false
        return
      }

      try {
        const response = await fetch('http://localhost:8000/api/history', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })

        if (!response.ok) {
          if (response.status === 401) {
            localStorage.removeItem('token')
            this.$emit('authExpired')
            return
          }
          throw new Error('获取历史记录失败')
        }

        this.records = await response.json()
      } catch (e) {
        console.error('获取历史记录失败:', e)
        this.error = e.message || '网络错误，请稍后重试'
      } finally {
        this.loading = false
      }
    },

    async viewRecord(record) {
      const token = localStorage.getItem('token')
      if (!token) {
        this.error = '请先登录'
        return
      }

      try {
        const response = await fetch(`http://localhost:8000/api/history/${record.id}`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })

        if (!response.ok) {
          throw new Error('获取记录详情失败')
        }

        const data = await response.json()
        this.$emit('viewRecord', data.result)
      } catch (e) {
        console.error('获取记录详情失败:', e)
        this.error = e.message || '获取记录详情失败'
      }
    },

    formatTime(isoString) {
      if (!isoString) return '-'
      try {
        const date = new Date(isoString)
        return date.toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        })
      } catch (e) {
        return isoString
      }
    },

    getScoreClass(score) {
      if (!score) return ''
      if (score >= 90) return 'excellent'
      if (score >= 75) return 'good'
      if (score >= 60) return 'average'
      return 'poor'
    },

    confirmDelete(record) {
      if (confirm(`确定要删除记录 "${record.filename}" 吗？`)) {
        this.deleteRecord(record)
      }
    },

    async deleteRecord(record) {
      const token = localStorage.getItem('token')
      if (!token) {
        this.error = '请先登录'
        return
      }

      try {
        const response = await fetch(`http://localhost:8000/api/history/${record.id}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })

        if (!response.ok) {
          if (response.status === 401) {
            localStorage.removeItem('token')
            this.$emit('authExpired')
            return
          }
          throw new Error('删除失败')
        }

        // 从列表中移除已删除的记录
        this.records = this.records.filter(r => r.id !== record.id)
      } catch (e) {
        console.error('删除记录失败:', e)
        this.error = e.message || '删除失败，请稍后重试'
      }
    }
  }
}
</script>

<style scoped>
.history-container {
  background: white;
  border-radius: 20px;
  padding: 2rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.history-header h2 {
  font-size: 1.5rem;
  color: #333;
  margin: 0;
}

.refresh-btn {
  padding: 0.5rem 1rem;
  border: 2px solid #667eea;
  background: white;
  color: #667eea;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.refresh-btn:hover:not(:disabled) {
  background: #667eea;
  color: white;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(102, 126, 234, 0.3);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 加载状态 */
.loading-state {
  text-align: center;
  padding: 3rem;
}

.loading-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 3rem;
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.empty-state h3 {
  color: #333;
  margin-bottom: 0.5rem;
}

.empty-state p {
  color: #666;
}

/* 记录列表 */
.records-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.record-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem;
  background: #f8fafc;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s;
  border: 2px solid transparent;
}

.record-card:hover {
  background: #f0f4ff;
  border-color: #667eea;
  transform: translateX(5px);
}

.record-icon {
  width: 50px;
  height: 50px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
}

.record-info {
  flex: 1;
  min-width: 0;
}

.record-filename {
  font-size: 1rem;
  font-weight: 600;
  color: #333;
  margin: 0 0 0.25rem 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.record-time {
  font-size: 0.85rem;
  color: #666;
  margin: 0;
}

.record-stats {
  display: flex;
  gap: 1.5rem;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-label {
  font-size: 0.75rem;
  color: #999;
}

.stat-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: #333;
}

.stat-value.excellent {
  color: #48bb78;
}

.stat-value.good {
  color: #667eea;
}

.stat-value.average {
  color: #ed8936;
}

.stat-value.poor {
  color: #f56565;
}

.record-arrow {
  color: #667eea;
  transition: transform 0.3s;
  cursor: pointer;
}

.record-card:hover .record-arrow {
  transform: translateX(5px);
}

/* 删除按钮 */
.delete-btn {
  background: none;
  border: none;
  padding: 0.5rem;
  cursor: pointer;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  opacity: 0.6;
}

.delete-btn:hover {
  background: rgba(229, 62, 62, 0.1);
  opacity: 1;
}

.delete-btn svg {
  transition: transform 0.2s;
}

.delete-btn:hover svg {
  transform: scale(1.1);
}

/* 错误提示 */
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
}

.error-message p {
  flex: 1;
  margin: 0;
  font-size: 0.9rem;
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

/* 响应式 */
@media (max-width: 600px) {
  .history-container {
    padding: 1.25rem;
  }

  .record-card {
    flex-wrap: wrap;
  }

  .record-stats {
    width: 100%;
    justify-content: space-around;
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid #e2e8f0;
  }

  .record-arrow {
    display: none;
  }
}
</style>