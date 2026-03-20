<template>
  <div class="settings-container">
    <div class="settings-header">
      <h2>⚙️ 用户设置</h2>
    </div>

    <!-- 用户信息卡片 -->
    <div class="settings-card profile-card">
      <h3>👤 个人信息</h3>
      <div class="profile-info">
        <div class="profile-item">
          <span class="profile-label">用户名</span>
          <span class="profile-value">{{ profile.username }}</span>
        </div>
        <div class="profile-item">
          <span class="profile-label">注册时间</span>
          <span class="profile-value">{{ formatDate(profile.created_at) }}</span>
        </div>
        <div class="profile-item">
          <span class="profile-label">分析记录数</span>
          <span class="profile-value">{{ profile.total_records }} 次</span>
        </div>
        <div class="profile-item" v-if="profile.latest_score">
          <span class="profile-label">最近得分</span>
          <span class="profile-value" :class="getScoreClass(profile.latest_score)">
            {{ profile.latest_score }} 分
          </span>
        </div>
      </div>
    </div>

    <!-- 睡眠目标设置 -->
    <div class="settings-card">
      <h3>🎯 睡眠目标</h3>
      <p class="card-desc">设置您的睡眠目标，系统会根据目标给出更精准的建议</p>
      
      <div class="setting-item">
        <label>目标睡眠时长</label>
        <div class="input-group">
          <input 
            type="number" 
            v-model.number="settings.target_sleep_hours" 
            min="4" 
            max="12" 
            step="0.5"
          />
          <span class="input-unit">小时</span>
        </div>
        <p class="setting-hint">建议成年人每晚睡眠 7-9 小时</p>
      </div>

      <div class="setting-item">
        <label>目标深睡眠比例</label>
        <div class="input-group">
          <input 
            type="number" 
            v-model.number="settings.target_deep_ratio" 
            min="0.1" 
            max="0.35" 
            step="0.01"
          />
          <span class="input-unit">{{ (settings.target_deep_ratio * 100).toFixed(0) }}%</span>
        </div>
        <p class="setting-hint">正常范围: 13-23%，深睡眠对身体恢复至关重要</p>
      </div>

      <div class="setting-item">
        <label>目标REM睡眠比例</label>
        <div class="input-group">
          <input 
            type="number" 
            v-model.number="settings.target_rem_ratio" 
            min="0.1" 
            max="0.35" 
            step="0.01"
          />
          <span class="input-unit">{{ (settings.target_rem_ratio * 100).toFixed(0) }}%</span>
        </div>
        <p class="setting-hint">正常范围: 20-25%，REM睡眠对记忆和情绪很重要</p>
      </div>

      <button @click="saveSettings" class="save-btn" :disabled="saving">
        <span v-if="saving" class="loading-spinner"></span>
        <span v-else>💾 保存设置</span>
      </button>
    </div>

    <!-- 修改密码 -->
    <div class="settings-card">
      <h3>🔐 修改密码</h3>
      
      <div class="setting-item">
        <label>当前密码</label>
        <input 
          type="password" 
          v-model="passwordForm.old_password" 
          placeholder="请输入当前密码"
        />
      </div>

      <div class="setting-item">
        <label>新密码</label>
        <input 
          type="password" 
          v-model="passwordForm.new_password" 
          placeholder="请输入新密码"
        />
      </div>

      <div class="setting-item">
        <label>确认新密码</label>
        <input 
          type="password" 
          v-model="passwordForm.confirm_password" 
          placeholder="请再次输入新密码"
        />
      </div>

      <button @click="changePassword" class="save-btn" :disabled="changingPassword">
        <span v-if="changingPassword" class="loading-spinner"></span>
        <span v-else>🔑 修改密码</span>
      </button>
    </div>

    <!-- 成功/错误提示 -->
    <transition name="fade">
      <div v-if="successMessage" class="message success">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="9" stroke="#48bb78" stroke-width="2"/>
          <path d="M6 10l3 3 5-6" stroke="#48bb78" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <p>{{ successMessage }}</p>
      </div>
    </transition>

    <transition name="fade">
      <div v-if="errorMessage" class="message error">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="9" stroke="#f56565" stroke-width="2"/>
          <path d="M10 6v4M10 14h.01" stroke="#f56565" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <p>{{ errorMessage }}</p>
        <button @click="errorMessage = null" class="close-message">×</button>
      </div>
    </transition>
  </div>
</template>

<script>
export default {
  name: 'Settings',
  data() {
    return {
      profile: {
        username: '',
        created_at: null,
        total_records: 0,
        latest_score: null
      },
      settings: {
        target_sleep_hours: 8.0,
        target_deep_ratio: 0.2,
        target_rem_ratio: 0.22,
        timezone: 'Asia/Shanghai'
      },
      passwordForm: {
        old_password: '',
        new_password: '',
        confirm_password: ''
      },
      saving: false,
      changingPassword: false,
      successMessage: null,
      errorMessage: null
    }
  },
  mounted() {
    this.fetchProfile()
    this.fetchSettings()
  },
  methods: {
    async fetchProfile() {
      const token = localStorage.getItem('token')
      if (!token) return

      try {
        const response = await fetch('http://localhost:8000/api/user/profile', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })

        if (response.ok) {
          this.profile = await response.json()
        } else if (response.status === 401) {
          localStorage.removeItem('token')
          this.$emit('authExpired')
        }
      } catch (e) {
        console.error('获取用户信息失败:', e)
      }
    },

    async fetchSettings() {
      const token = localStorage.getItem('token')
      if (!token) return

      try {
        const response = await fetch('http://localhost:8000/api/user/settings', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })

        if (response.ok) {
          const data = await response.json()
          this.settings = { ...this.settings, ...data }
        }
      } catch (e) {
        console.error('获取设置失败:', e)
      }
    },

    async saveSettings() {
      this.saving = true
      this.successMessage = null
      this.errorMessage = null

      const token = localStorage.getItem('token')
      if (!token) {
        this.errorMessage = '请先登录'
        this.saving = false
        return
      }

      try {
        const response = await fetch('http://localhost:8000/api/user/settings', {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(this.settings)
        })

        if (response.ok) {
          this.successMessage = '设置已保存'
          setTimeout(() => { this.successMessage = null }, 3000)
        } else if (response.status === 401) {
          localStorage.removeItem('token')
          this.$emit('authExpired')
        } else {
          const data = await response.json()
          this.errorMessage = data.detail || '保存失败'
        }
      } catch (e) {
        this.errorMessage = '网络错误，请稍后重试'
      } finally {
        this.saving = false
      }
    },

    async changePassword() {
      // 验证
      if (!this.passwordForm.old_password || !this.passwordForm.new_password) {
        this.errorMessage = '请填写完整密码信息'
        return
      }

      if (this.passwordForm.new_password !== this.passwordForm.confirm_password) {
        this.errorMessage = '两次输入的新密码不一致'
        return
      }

      if (this.passwordForm.new_password.length < 6) {
        this.errorMessage = '密码长度至少6位'
        return
      }

      this.changingPassword = true
      this.successMessage = null
      this.errorMessage = null

      const token = localStorage.getItem('token')
      if (!token) {
        this.errorMessage = '请先登录'
        this.changingPassword = false
        return
      }

      try {
        const response = await fetch('http://localhost:8000/api/user/password', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            old_password: this.passwordForm.old_password,
            new_password: this.passwordForm.new_password
          })
        })

        if (response.ok) {
          this.successMessage = '密码修改成功'
          this.passwordForm = {
            old_password: '',
            new_password: '',
            confirm_password: ''
          }
          setTimeout(() => { this.successMessage = null }, 3000)
        } else if (response.status === 401) {
          localStorage.removeItem('token')
          this.$emit('authExpired')
        } else {
          const data = await response.json()
          this.errorMessage = data.detail || '修改失败'
        }
      } catch (e) {
        this.errorMessage = '网络错误，请稍后重试'
      } finally {
        this.changingPassword = false
      }
    },

    formatDate(isoString) {
      if (!isoString) return '-'
      try {
        const date = new Date(isoString)
        return date.toLocaleDateString('zh-CN', {
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        })
      } catch (e) {
        return isoString
      }
    },

    getScoreClass(score) {
      if (score >= 90) return 'excellent'
      if (score >= 75) return 'good'
      if (score >= 60) return 'average'
      return 'poor'
    }
  }
}
</script>

<style scoped>
.settings-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.settings-header h2 {
  font-size: 1.5rem;
  color: #333;
  margin: 0;
}

.settings-card {
  background: white;
  border-radius: 20px;
  padding: 2rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
}

.settings-card h3 {
  font-size: 1.2rem;
  color: #333;
  margin-bottom: 0.5rem;
}

.card-desc {
  color: #666;
  font-size: 0.9rem;
  margin-bottom: 1.5rem;
}

/* 个人信息卡片 */
.profile-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.profile-card h3 {
  color: white;
}

.profile-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.profile-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.profile-label {
  font-size: 0.85rem;
  opacity: 0.8;
}

.profile-value {
  font-size: 1.1rem;
  font-weight: 600;
}

.profile-value.excellent { color: #9ae6b4; }
.profile-value.good { color: #90cdf4; }
.profile-value.average { color: #fbd38d; }
.profile-value.poor { color: #feb2b2; }

/* 设置项 */
.setting-item {
  margin-bottom: 1.5rem;
}

.setting-item label {
  display: block;
  font-weight: 500;
  color: #333;
  margin-bottom: 0.5rem;
}

.input-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.input-group input {
  flex: 1;
  max-width: 150px;
}

.input-unit {
  color: #666;
  font-size: 0.9rem;
  min-width: 50px;
}

.setting-item input[type="number"],
.setting-item input[type="password"] {
  width: 100%;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  transition: all 0.3s;
}

.setting-item input:focus {
  outline: none;
  border-color: #667eea;
  background: white;
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
}

.setting-hint {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #888;
}

/* 保存按钮 */
.save-btn {
  width: 100%;
  padding: 1rem;
  font-size: 1rem;
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

.save-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
}

.save-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 消息提示 */
.message {
  padding: 1rem 1.25rem;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.95rem;
}

.message.success {
  background: #f0fff4;
  border: 1px solid #9ae6b4;
  color: #276749;
}

.message.error {
  background: #fff5f5;
  border: 1px solid #feb2b2;
  color: #c53030;
}

.message p {
  flex: 1;
  margin: 0;
}

.close-message {
  background: none;
  border: none;
  font-size: 1.25rem;
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

.close-message:hover {
  background: rgba(197, 48, 48, 0.1);
}

/* 过渡动画 */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

/* 响应式 */
@media (max-width: 600px) {
  .settings-card {
    padding: 1.5rem;
  }
  
  .profile-info {
    grid-template-columns: 1fr;
  }
  
  .input-group input {
    max-width: none;
  }
}
</style>