<template>
  <div id="app">
    <!-- 顶部导航栏 -->
    <header class="navbar">
      <div class="logo">
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <path d="M16 4C9.373 4 4 9.373 4 16s5.373 12 12 12 12-5.373 12-12S22.627 4 16 4zm0 2c5.523 0 10 4.477 10 10s-4.477 10-10 10S6 21.523 6 16 10.477 6 16 6z" fill="#667eea"/>
          <path d="M16 10v6l4 2" stroke="#667eea" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span>睡眠分析系统</span>
      </div>
      <nav class="nav-links">
        <a href="#" :class="{ active: currentView === 'upload' }" @click.prevent="setView('upload')">分析</a>
        <a href="#" :class="{ active: currentView === 'history', disabled: !isAuthenticated }" @click.prevent="isAuthenticated && setView('history')">历史记录</a>
        <!-- <a href="#">关于</a> -->
      </nav>
      <div class="user-actions">
        <template v-if="isAuthenticated">
          <span class="user-greeting">欢迎，{{ username }}</span>
          <button @click="logout" class="logout-btn">登出</button>
        </template>
        <template v-else>
          <button @click="showLogin" class="auth-btn">登录</button>
          <button @click="showRegister" class="auth-btn register">注册</button>
        </template>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="container">
      <Auth v-if="!isAuthenticated" @authenticated="handleAuth" :initialMode="authMode" ref="authComponent" />
      
      <div v-else>
        <!-- 历史记录视图 -->
        <template v-if="currentView === 'history'">
          <History @viewRecord="handleViewRecord" @authExpired="handleAuthExpired" />
        </template>
        
        <!-- 上传分析视图 -->
        <template v-else>
          <FileUpload @analysisComplete="handleAnalysisComplete" @authExpired="handleAuthExpired" />
          
          <transition name="fade">
            <Hypnogram v-if="resultData" :data="resultData" />
          </transition>
        </template>
      </div>
    </main>

    <!-- 页脚 -->
    <footer class="footer">
      <p>&copy; 2026 睡眠分析系统 | Powered by Vue 3 + FastAPI</p>
    </footer>
  </div>
</template>

<script>
import FileUpload from './components/FileUpload.vue'
import Hypnogram from './components/Hypnogram.vue'
import Auth from './components/Auth.vue'
import History from './components/History.vue'

export default {
  name: 'App',
  components: {
    FileUpload,
    Hypnogram,
    Auth,
    History
  },
  data() {
    return {
      resultData: null,
      isAuthenticated: !!localStorage.getItem('token'),
      username: localStorage.getItem('username') || '',
      authMode: 'login',  // 'login' 或 'register'
      currentView: 'upload'  // 'upload' 或 'history'
    }
  },
  methods: {
    handleAuth(user) {
      this.isAuthenticated = true
      this.username = user || '用户'
      localStorage.setItem('username', this.username)
    },
    handleAnalysisComplete(data) {
      this.resultData = data
    },
    handleAuthExpired() {
      this.isAuthenticated = false
      this.username = ''
      this.resultData = null
      this.currentView = 'upload'
      localStorage.removeItem('token')
      localStorage.removeItem('username')
    },
    logout() {
      this.isAuthenticated = false
      this.username = ''
      this.resultData = null
      this.currentView = 'upload'
      localStorage.removeItem('token')
      localStorage.removeItem('username')
    },
    showLogin() {
      this.authMode = 'login'
      this.isAuthenticated = false
    },
    showRegister() {
      this.authMode = 'register'
      this.isAuthenticated = false
    },
    setView(view) {
      if (this.isAuthenticated) {
        this.currentView = view
        // 切换到上传视图时清除结果数据
        if (view === 'upload') {
          this.resultData = null
        }
      }
    },
    handleViewRecord(result) {
      // 从历史记录点击查看详情，切换到上传视图并显示结果
      this.currentView = 'upload'
      this.resultData = result
    }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 导航栏 */
.navbar {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.25rem;
  font-weight: 600;
  color: #333;
}

.nav-links {
  display: flex;
  gap: 2rem;
}

.nav-links a {
  color: #666;
  text-decoration: none;
  transition: color 0.3s;
  font-weight: 500;
}

.nav-links a:hover,
.nav-links a.active {
  color: #667eea;
}

.nav-links a.disabled {
  color: #ccc;
  cursor: not-allowed;
}

/* 用户操作区 */
.user-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-greeting {
  color: #667eea;
  font-weight: 500;
}

.auth-btn {
  padding: 0.5rem 1.25rem;
  border: 2px solid #667eea;
  background: transparent;
  color: #667eea;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
}

.auth-btn:hover {
  background: #667eea;
  color: white;
}

.auth-btn.register {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: white;
}

.auth-btn.register:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.logout-btn {
  padding: 0.5rem 1.25rem;
  border: 2px solid #e53e3e;
  background: transparent;
  color: #e53e3e;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
}

.logout-btn:hover {
  background: #e53e3e;
  color: white;
}

/* 主容器 */
.container {
  flex: 1;
  max-width: 1400px;
  margin: 2rem auto;
  padding: 0 2rem;
  width: 100%;
}

/* 页脚 */
.footer {
  background: rgba(0, 0, 0, 0.2);
  color: white;
  text-align: center;
  padding: 1.5rem;
  margin-top: 2rem;
}

/* 过渡动画 */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.5s ease, transform 0.5s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}
</style>
