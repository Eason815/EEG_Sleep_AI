<template>
  <div class="regulation-container">
    <div class="regulation-header">
      <div>
        <h2>调控中心</h2>
        <p class="header-desc">基于最近一次核心睡眠结果，生成模拟智能家居调控方案。</p>
      </div>
      <div class="header-actions">
        <button class="secondary-btn" @click="resetSimulation" :disabled="!plan">恢复环境</button>
        <button class="primary-btn" @click="applyStrategy" :disabled="!plan">一键应用策略</button>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="loading-icon">...</div>
      <p>正在生成调控策略...</p>
    </div>

    <div v-else-if="emptyMessage" class="empty-state">
      <div class="empty-icon">Zz</div>
      <h3>暂无可用调控方案</h3>
      <p>{{ emptyMessage }}</p>
    </div>

    <template v-else-if="plan">
      <div class="overview-grid">
        <div class="overview-card emphasis">
          <p class="card-label">当前场景</p>
          <h3>{{ plan.scene.name }}</h3>
          <p class="card-desc">{{ plan.scene.goal }}</p>
          <p class="reason-text">{{ plan.scene.reason }}</p>
        </div>
        <div class="overview-card">
          <p class="card-label">最新记录</p>
          <h3>{{ sourceRecord?.filename || '最近一次记录' }}</h3>
          <p class="card-desc">{{ formatDate(sourceRecord?.created_at) }}</p>
        </div>
        <div class="overview-card">
          <p class="card-label">睡眠评分</p>
          <h3>{{ plan.sleep_snapshot.quality_score }} 分</h3>
          <p class="card-desc">核心睡眠时长 {{ plan.sleep_snapshot.duration_hours.toFixed(1) }} 小时</p>
        </div>
      </div>

      <div class="snapshot-grid">
        <div class="snapshot-card">
          <span>深睡比例</span>
          <strong>{{ formatPercent(plan.sleep_snapshot.deep_ratio) }}</strong>
        </div>
        <div class="snapshot-card">
          <span>REM 比例</span>
          <strong>{{ formatPercent(plan.sleep_snapshot.rem_ratio) }}</strong>
        </div>
        <div class="snapshot-card">
          <span>入睡潜伏期</span>
          <strong>{{ plan.sleep_snapshot.sleep_latency_min.toFixed(0) }} 分钟</strong>
        </div>
        <div class="snapshot-card">
          <span>夜醒次数</span>
          <strong>{{ plan.sleep_snapshot.num_awakenings }} 次</strong>
        </div>
      </div>

      <div class="content-grid">
        <div class="panel">
          <div class="panel-header">
            <h3>问题识别</h3>
            <span class="panel-note">{{ plan.issues.length }} 项</span>
          </div>
          <div v-if="plan.issues.length" class="issue-list">
            <div v-for="issue in plan.issues" :key="issue.title" class="issue-item" :class="issue.severity">
              <div class="issue-title-row">
                <strong>{{ issue.label }}</strong>
                <span class="severity-tag">{{ severityLabel(issue.severity) }}</span>
              </div>
              <p>{{ issue.detail }}</p>
            </div>
          </div>
          <div v-else class="success-box">
            <strong>当前睡眠状态较稳定</strong>
            <p>系统建议保持舒眠巩固模式，重点维持稳定环境。</p>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <h3>预期收益</h3>
            <span class="panel-note">模拟估计</span>
          </div>
          <div class="benefit-list">
            <div v-for="benefit in plan.expected_benefits" :key="benefit" class="benefit-item">
              {{ benefit }}
            </div>
          </div>
        </div>
      </div>

      <div class="device-panel">
        <div class="panel-header">
          <h3>智能家居联动模拟</h3>
          <span class="panel-note">当前为演示环境，不依赖真实硬件</span>
        </div>
        <div class="device-grid">
          <div v-for="(device, key) in simulatedState" :key="key" class="device-card">
            <div class="device-top">
              <div>
                <h4>{{ device.label }}</h4>
                <p class="device-current">当前: {{ displayValue(device) }}</p>
              </div>
              <span class="target-badge">目标 {{ displayValue(plan.device_targets[key]) }}</span>
            </div>

            <template v-if="device.type === 'range'">
              <input
                class="slider"
                type="range"
                :min="device.min"
                :max="device.max"
                :step="device.step"
                :value="device.value"
                @input="updateRange(key, $event.target.value)"
              />
            </template>
            <template v-else>
              <button class="toggle-btn" :class="{ active: device.value }" @click="toggleDevice(key)">
                {{ device.value ? '已开启' : '已关闭' }}
              </button>
            </template>
          </div>
        </div>
      </div>

      <div class="content-grid">
        <div class="panel">
          <div class="panel-header">
            <h3>自动联动时间线</h3>
            <span class="panel-note">策略执行脚本</span>
          </div>
          <div class="timeline">
            <div v-for="item in plan.automation_timeline" :key="`${item.time}-${item.action}`" class="timeline-item">
              <span class="time-chip">{{ item.time }}</span>
              <p>{{ item.action }}</p>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <h3>模拟执行日志</h3>
            <span class="panel-note">前端本地回放</span>
          </div>
          <div class="log-list">
            <div v-for="log in activityLogs" :key="log" class="log-item">{{ log }}</div>
          </div>
        </div>
      </div>
    </template>

    <div v-if="error" class="error-message">
      <p>{{ error }}</p>
      <button @click="error = null" class="close-error">x</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Regulation',
  data() {
    return {
      loading: false,
      error: null,
      emptyMessage: null,
      plan: null,
      sourceRecord: null,
      simulatedState: {},
      activityLogs: []
    }
  },
  mounted() {
    this.fetchPlan()
  },
  methods: {
    async fetchPlan() {
      this.loading = true
      this.error = null
      this.emptyMessage = null

      const token = localStorage.getItem('token')
      if (!token) {
        this.error = '请先登录'
        this.loading = false
        return
      }

      try {
        const response = await fetch('http://localhost:8000/api/regulation/plan', {
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
          throw new Error('获取调控方案失败')
        }

        const data = await response.json()
        if (!data.has_plan) {
          this.plan = null
          this.emptyMessage = data.message || '暂无可用方案'
          return
        }

        this.plan = data.plan
        this.sourceRecord = data.source_record
        this.simulatedState = this.cloneState(data.plan.baseline_state)
        this.activityLogs = [
          '已加载最近一次睡眠分析结果。',
          `推荐场景: ${data.plan.scene.name}`,
          '可点击“一键应用策略”查看外设联动效果。'
        ]
      } catch (e) {
        this.error = e.message || '网络错误，请稍后重试'
      } finally {
        this.loading = false
      }
    },

    cloneState(value) {
      return JSON.parse(JSON.stringify(value || {}))
    },

    applyStrategy() {
      if (!this.plan) return
      this.simulatedState = this.cloneState(this.plan.device_targets)
      this.activityLogs = [
        `策略已应用: ${this.plan.scene.name}`,
        ...this.plan.automation_timeline.map(item => `${item.time} ${item.action}`)
      ]
    },

    resetSimulation() {
      if (!this.plan) return
      this.simulatedState = this.cloneState(this.plan.baseline_state)
      this.activityLogs = [
        '模拟环境已恢复为默认卧室状态。',
        '你可以手动调节参数，或再次应用自动策略。'
      ]
    },

    updateRange(key, value) {
      if (!this.simulatedState[key]) return
      this.simulatedState[key].value = Number(value)
    },

    toggleDevice(key) {
      if (!this.simulatedState[key]) return
      this.simulatedState[key].value = !this.simulatedState[key].value
    },

    displayValue(device) {
      if (!device) return '-'
      if (device.type === 'toggle') {
        return device.value ? '开启' : '关闭'
      }
      const precision = device.step === 0.5 ? 1 : 0
      return `${Number(device.value).toFixed(precision)}${device.unit}`
    },

    formatPercent(value) {
      return `${((value || 0) * 100).toFixed(1)}%`
    },

    formatDate(value) {
      if (!value) return '-'
      return new Date(value).toLocaleString('zh-CN')
    },

    severityLabel(level) {
      if (level === 'high') return '高优先级'
      if (level === 'medium') return '中优先级'
      return '提示'
    }
  }
}
</script>

<style scoped>
.regulation-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.regulation-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  background: white;
  border-radius: 20px;
  padding: 1.75rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
}

.regulation-header h2 {
  margin: 0 0 0.4rem;
  font-size: 1.6rem;
  color: #24324b;
}

.header-desc {
  margin: 0;
  color: #61708a;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
}

.primary-btn,
.secondary-btn,
.toggle-btn {
  border: none;
  border-radius: 12px;
  padding: 0.85rem 1.2rem;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.25s ease;
}

.primary-btn {
  background: linear-gradient(135deg, #1f6feb, #2ea043);
  color: white;
}

.secondary-btn {
  background: #eef3ff;
  color: #3555a7;
}

.primary-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.overview-grid,
.snapshot-grid,
.content-grid,
.device-grid {
  display: grid;
  gap: 1rem;
}

.overview-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.snapshot-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.content-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.device-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.overview-card,
.snapshot-card,
.panel,
.device-panel {
  background: white;
  border-radius: 20px;
  padding: 1.5rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
}

.overview-card.emphasis {
  background: linear-gradient(135deg, #183b66, #2260aa);
  color: white;
}

.card-label,
.panel-note,
.card-desc,
.reason-text {
  color: inherit;
}

.card-label {
  font-size: 0.85rem;
  opacity: 0.75;
  margin-bottom: 0.5rem;
}

.card-desc,
.reason-text,
.snapshot-card span {
  color: #6b778c;
}

.overview-card.emphasis .card-desc,
.overview-card.emphasis .reason-text,
.overview-card.emphasis .card-label {
  color: rgba(255, 255, 255, 0.85);
}

.snapshot-card strong {
  display: block;
  margin-top: 0.5rem;
  font-size: 1.35rem;
  color: #1f2f4a;
}

.panel-header,
.device-top,
.issue-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.panel-header h3,
.device-top h4 {
  margin: 0;
  color: #24324b;
}

.issue-list,
.benefit-list,
.timeline,
.log-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1rem;
}

.issue-item,
.benefit-item,
.timeline-item,
.log-item,
.success-box {
  border-radius: 14px;
  padding: 1rem;
  background: #f6f8fc;
}

.issue-item.high {
  background: #fff1f1;
}

.issue-item.medium {
  background: #fff7eb;
}

.issue-item p,
.success-box p,
.timeline-item p {
  margin: 0.35rem 0 0;
  color: #5b6780;
  line-height: 1.55;
}

.severity-tag,
.target-badge,
.time-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 0.25rem 0.65rem;
  font-size: 0.8rem;
}

.severity-tag {
  background: rgba(31, 111, 235, 0.12);
  color: #1f6feb;
}

.target-badge {
  background: #edf8ef;
  color: #2d8a48;
}

.time-chip {
  background: #eef3ff;
  color: #3555a7;
  min-width: 64px;
}

.device-card {
  background: #f6f8fc;
  border-radius: 16px;
  padding: 1rem;
}

.device-current {
  margin: 0.35rem 0 0;
  color: #5b6780;
}

.slider {
  width: 100%;
  margin-top: 1rem;
}

.toggle-btn {
  margin-top: 1rem;
  width: 100%;
  background: #dbe3f5;
  color: #37507e;
}

.toggle-btn.active {
  background: #dff5e5;
  color: #207245;
}

.loading-state,
.empty-state {
  background: white;
  border-radius: 20px;
  padding: 3rem 1.5rem;
  text-align: center;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
}

.error-message {
  background: #fff1f1;
  color: #c23c3c;
  border-radius: 16px;
  padding: 1rem 1.25rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.close-error {
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
}

@media (max-width: 1100px) {
  .overview-grid,
  .content-grid,
  .device-grid,
  .snapshot-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .regulation-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    flex-direction: column;
  }
}
</style>
