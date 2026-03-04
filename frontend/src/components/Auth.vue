<template>
  <div class="auth-wrapper">
    <div class="auth-card">
      <!-- 头部图标和标题 -->
      <div class="auth-header">
        <div class="auth-icon">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="20" fill="url(#gradient)" opacity="0.2"/>
            <path d="M24 8C15.163 8 8 15.163 8 24s7.163 16 16 16 16-7.163 16-16S32.837 8 24 8zm0 4c6.627 0 12 5.373 12 12s-5.373 12-12 12-12-5.373-12-12 5.373-12 12-12z" fill="url(#gradient)"/>
            <path d="M24 16v8l6 4" stroke="url(#gradient)" stroke-width="2.5" stroke-linecap="round"/>
            <defs>
              <linearGradient id="gradient" x1="8" y1="8" x2="40" y2="40">
                <stop stop-color="#667eea"/>
                <stop offset="1" stop-color="#764ba2"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <h2 class="auth-title">{{ isLogin ? '欢迎回来' : '创建账号' }}</h2>
        <p class="auth-subtitle">{{ isLogin ? '登录以继续使用睡眠分析系统' : '注册新账号开始您的睡眠分析之旅' }}</p>
      </div>

      <!-- 表单区域 -->
      <form @submit.prevent="handleSubmit" class="auth-form">
        <div class="input-group">
          <div class="input-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M10 10c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="#667eea"/>
            </svg>
          </div>
          <input 
            v-model="username" 
            placeholder="用户名" 
            required 
            class="auth-input"
            :class="{ 'has-value': username }"
          />
        </div>

        <div class="input-group">
          <div class="input-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M15 8H5c-1.1 0-2 .9-2 2v6c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2v-6c0-1.1-.9-2-2-2zm0 0V6c0-2.21-1.79-4-4-4S7 3.79 7 6v2h8zM10 4c1.1 0 2 .9 2 2v2H8V6c0-1.1.9-2 2-2z" fill="#667eea"/>
            </svg>
          </div>
          <input 
            v-model="password" 
            :type="showPassword ? 'text' : 'password'" 
            placeholder="密码" 
            required 
            class="auth-input"
            :class="{ 'has-value': password }"
          />
          <button type="button" class="toggle-password" @click="showPassword = !showPassword">
            <svg v-if="!showPassword" width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M10 4.5C5.5 4.5 1.73 7.61.5 10c1.23 2.39 5 5.5 9.5 5.5s8.27-3.11 9.5-5.5c-1.23-2.39-5-5.5-9.5-5.5zm0 9c-1.93 0-3.5-1.57-3.5-3.5S8.07 6.5 10 6.5s3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z" fill="#999"/>
              <circle cx="10" cy="10" r="1.5" fill="#999"/>
            </svg>
            <svg v-else width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M3.73 5.27L1.5 7.5l1.41 1.41L5.14 6.7C6.55 5.87 8.2 5.5 10 5.5c4.5 0 8.27 3.11 9.5 5.5-.55 1.07-1.41 2.14-2.5 3.05l2.09 2.09 1.41-1.41-1.64-1.64C17.37 12.14 18.5 10.95 19.5 10c-1.23-2.39-5-5.5-9.5-5.5-1.28 0-2.5.22-3.64.61L3.73 5.27zM1.5 1.5L.09 2.91l2.64 2.64C1.41 6.55.55 7.62 0 8.69c1.23 2.39 5 5.5 9.5 5.5 1.8 0 3.45-.37 4.86-1.2l2.64 2.64 1.41-1.41L1.5 1.5zm7.91 5.32c-.59.34-1 .95-1 1.68 0 1.1.9 2 2 2 .73 0 1.34-.41 1.68-1l-2.68-2.68z" fill="#667eea"/>
            </svg>
          </button>
        </div>

        <button type="submit" class="submit-btn" :disabled="loading">
          <span v-if="loading" class="loading-spinner"></span>
          <span v-else>{{ isLogin ? '登 录' : '注 册' }}</span>
        </button>
      </form>

      <!-- 错误提示 -->
      <transition name="fade">
        <div v-if="errorMessage" class="error-message">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="9" stroke="#f56565" stroke-width="2"/>
            <path d="M10 6v4M10 14h.01" stroke="#f56565" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <p>{{ errorMessage }}</p>
          <button @click="errorMessage = null" class="close-error">×</button>
        </div>
      </transition>

      <!-- 切换登录/注册 -->
      <div class="auth-switch">
        <p>
          {{ isLogin ? '还没有账号？' : '已有账号？' }}
          <span class="switch-link" @click="toggleMode">
            {{ isLogin ? '立即注册' : '立即登录' }}
          </span>
        </p>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    initialMode: {
      type: String,
      default: 'login'
    }
  },
  data() {
    return {
      isLogin: this.initialMode === 'login',
      username: '',
      password: '',
      showPassword: false,
      loading: false,
      errorMessage: null
    }
  },
  watch: {
    initialMode(newVal) {
      this.isLogin = newVal === 'login'
    }
  },
  methods: {
    toggleMode() {
      this.isLogin = !this.isLogin
      this.errorMessage = null
    },
    async handleSubmit() {
      if (this.loading) return
      
      this.loading = true
      this.errorMessage = null
      
      const endpoint = this.isLogin ? '/api/login' : '/api/register'
      const formData = new FormData()
      formData.append('username', this.username)
      formData.append('password', this.password)
      
      try {
        const response = await fetch(`http://localhost:8000${endpoint}`, {
          method: 'POST',
          body: formData
        })
        const data = await response.json()
        
        if (response.ok) {
          if (this.isLogin) {
            localStorage.setItem('token', data.access_token)
            this.$emit('authenticated', this.username)
          } else {
            this.errorMessage = '注册成功！请登录'
            this.isLogin = true
          }
        } else {
          this.errorMessage = data.detail || '操作失败，请重试'
        }
      } catch (e) {
        this.errorMessage = '网络错误，请检查连接'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.auth-wrapper {
  min-height: calc(100vh - 200px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.auth-card {
  background: white;
  border-radius: 20px;
  padding: 2.5rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 420px;
}

/* 头部样式 */
.auth-header {
  text-align: center;
  margin-bottom: 2rem;
}

.auth-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
  border-radius: 50%;
  margin-bottom: 1rem;
}

.auth-title {
  font-size: 1.75rem;
  font-weight: 600;
  color: #333;
  margin-bottom: 0.5rem;
}

.auth-subtitle {
  color: #666;
  font-size: 0.95rem;
}

/* 表单样式 */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.input-group {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.auth-input {
  width: 100%;
  padding: 1rem 1rem 1rem 3rem;
  font-size: 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  transition: all 0.3s;
  color: #333;
}

.auth-input:focus {
  outline: none;
  border-color: #667eea;
  background: white;
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
}

.auth-input::placeholder {
  color: #a0aec0;
}

.toggle-password {
  position: absolute;
  right: 1rem;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.6;
  transition: opacity 0.3s;
}

.toggle-password:hover {
  opacity: 1;
}

/* 提交按钮 */
.submit-btn {
  width: 100%;
  padding: 1rem;
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
  margin-top: 0.5rem;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.7;
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
  to { transform: rotate(360deg); }
}

/* 错误提示 */
.error-message {
  margin-top: 1rem;
  padding: 0.875rem 1rem;
  background: #fff5f5;
  border: 1px solid #feb2b2;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: #c53030;
  font-size: 0.9rem;
}

.error-message p {
  flex: 1;
  margin: 0;
}

.close-error {
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

.close-error:hover {
  background: rgba(197, 48, 48, 0.1);
}

/* 切换链接 */
.auth-switch {
  text-align: center;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid #e2e8f0;
}

.auth-switch p {
  color: #666;
  font-size: 0.95rem;
}

.switch-link {
  color: #667eea;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.3s;
}

.switch-link:hover {
  color: #764ba2;
  text-decoration: underline;
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
@media (max-width: 480px) {
  .auth-card {
    padding: 1.5rem;
  }
  
  .auth-title {
    font-size: 1.5rem;
  }
  
  .auth-icon {
    width: 64px;
    height: 64px;
  }
  
  .auth-icon svg {
    width: 36px;
    height: 36px;
  }
}
</style>