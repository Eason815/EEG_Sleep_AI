<template>
  <div class="trends-container">
    <div class="trends-header">
      <h2>📈 睡眠趋势分析</h2>
      <div class="period-selector">
        <button 
          :class="{ active: period === 'week' }" 
          @click="changePeriod('week')">
          最近7天
        </button>
        <button 
          :class="{ active: period === 'month' }" 
          @click="changePeriod('month')">
          最近30天
        </button>
        <button 
          :class="{ active: period === 'all' }" 
          @click="changePeriod('all')">
          全部
        </button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <div class="loading-icon">⏳</div>
      <p>加载趋势数据...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading && !summary" class="empty-state">
      <div class="empty-icon">📊</div>
      <h3>暂无数据</h3>
      <p>开始您的第一次睡眠分析，即可查看趋势数据</p>
    </div>

    <!-- 数据展示 -->
    <template v-else>
      <!-- 汇总卡片 -->
      <div class="summary-cards">
        <div class="summary-card">
          <div class="summary-icon">📝</div>
          <div class="summary-content">
            <p class="summary-label">分析次数</p>
            <p class="summary-value">{{ summary.total_records }}</p>
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-icon">⭐</div>
          <div class="summary-content">
            <p class="summary-label">平均质量</p>
            <p class="summary-value" :class="getScoreClass(summary.avg_quality_score)">
              {{ summary.avg_quality_score.toFixed(1) }}
            </p>
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-icon">⏰</div>
          <div class="summary-content">
            <p class="summary-label">平均时长</p>
            <p class="summary-value">{{ summary.avg_duration_hours.toFixed(1) }}h</p>
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-icon">🏆</div>
          <div class="summary-content">
            <p class="summary-label">最佳得分</p>
            <p class="summary-value excellent">{{ summary.best_score }}</p>
          </div>
        </div>
      </div>

      <!-- 图表区域 -->
      <div class="charts-grid">
        <!-- 质量趋势图 -->
        <div class="chart-card">
          <h3>📊 睡眠质量趋势</h3>
          <div ref="qualityChart" style="width: 100%; height: 300px;"></div>
        </div>

        <!-- 睡眠时长图 -->
        <div class="chart-card">
          <h3>⏰ 睡眠时长变化</h3>
          <div ref="durationChart" style="width: 100%; height: 300px;"></div>
        </div>

        <!-- 睡眠结构堆叠图 -->
        <div class="chart-card full-width">
          <h3>🌙 睡眠结构变化</h3>
          <div ref="structureChart" style="width: 100%; height: 350px;"></div>
        </div>
      </div>

      <!-- 平均睡眠结构 -->
      <div class="avg-structure-card">
        <h3>💡 平均睡眠结构</h3>
        <div class="structure-bars">
          <div class="structure-bar">
            <span class="bar-label">深睡眠</span>
            <div class="bar-container">
              <div class="bar-fill deep" :style="{ width: (summary.avg_stats.Deep_ratio * 100) + '%' }"></div>
            </div>
            <span class="bar-value">{{ (summary.avg_stats.Deep_ratio * 100).toFixed(1) }}%</span>
          </div>
          <div class="structure-bar">
            <span class="bar-label">REM睡眠</span>
            <div class="bar-container">
              <div class="bar-fill rem" :style="{ width: (summary.avg_stats.REM_ratio * 100) + '%' }"></div>
            </div>
            <span class="bar-value">{{ (summary.avg_stats.REM_ratio * 100).toFixed(1) }}%</span>
          </div>
          <div class="structure-bar">
            <span class="bar-label">浅睡眠</span>
            <div class="bar-container">
              <div class="bar-fill light" :style="{ width: (summary.avg_stats.Light_ratio * 100) + '%' }"></div>
            </div>
            <span class="bar-value">{{ (summary.avg_stats.Light_ratio * 100).toFixed(1) }}%</span>
          </div>
          <div class="structure-bar">
            <span class="bar-label">清醒</span>
            <div class="bar-container">
              <div class="bar-fill wake" :style="{ width: (summary.avg_stats.W_ratio * 100) + '%' }"></div>
            </div>
            <span class="bar-value">{{ (summary.avg_stats.W_ratio * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </div>
    </template>

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
import * as echarts from 'echarts'

export default {
  name: 'Trends',
  data() {
    return {
      period: 'week',
      loading: false,
      error: null,
      summary: null,
      chartData: null,
      qualityChart: null,
      durationChart: null,
      structureChart: null
    }
  },
  mounted() {
    this.fetchTrends()
    window.addEventListener('resize', this.handleResize)
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.handleResize)
    this.qualityChart?.dispose()
    this.durationChart?.dispose()
    this.structureChart?.dispose()
  },
  methods: {
    handleResize() {
      this.qualityChart?.resize()
      this.durationChart?.resize()
      this.structureChart?.resize()
    },
    
    async fetchTrends() {
      this.loading = true
      this.error = null
      
      const token = localStorage.getItem('token')
      if (!token) {
        this.error = '请先登录'
        this.loading = false
        return
      }

      try {
        const response = await fetch(`http://localhost:8000/api/trends?period=${this.period}`, {
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
          throw new Error('获取趋势数据失败')
        }

        const data = await response.json()
        this.summary = data.summary
        this.chartData = data.chart_data
        this.loading = false

        if (this.summary) {
          await this.$nextTick()
          this.renderCharts()
        }
        return
      } catch (e) {
        console.error('获取趋势数据失败:', e)
        this.error = e.message || '网络错误，请稍后重试'
      } finally {
        if (this.loading) {
          this.loading = false
        }
      }
    },

    changePeriod(newPeriod) {
      this.period = newPeriod
      this.fetchTrends()
    },

    renderCharts() {
      this.renderQualityChart()
      this.renderDurationChart()
      this.renderStructureChart()
    },

    renderQualityChart() {
      if (!this.$refs.qualityChart || !this.chartData) return
      
      if (!this.qualityChart) {
        this.qualityChart = echarts.init(this.$refs.qualityChart)
      }

      const option = {
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          borderColor: '#ddd',
          borderWidth: 1,
          textStyle: { color: '#333' }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          top: '10%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: this.chartData.dates,
          axisLine: { lineStyle: { color: '#ddd' } },
          axisLabel: { color: '#666', rotate: 30 }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 100,
          axisLine: { lineStyle: { color: '#ddd' } },
          axisLabel: { color: '#666' },
          splitLine: { lineStyle: { type: 'dashed' } }
        },
        series: [{
          name: '质量分数',
          data: this.chartData.quality_scores,
          type: 'line',
          smooth: true,
          lineStyle: {
            width: 3,
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: '#667eea' },
              { offset: 1, color: '#764ba2' }
            ])
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(102, 126, 234, 0.3)' },
              { offset: 1, color: 'rgba(118, 75, 162, 0.05)' }
            ])
          },
          itemStyle: {
            color: '#667eea'
          },
          markLine: {
            data: [{ type: 'average', name: '平均值' }],
            lineStyle: { color: '#ed8936', type: 'dashed' }
          }
        }]
      }

      this.qualityChart.setOption(option)
    },

    renderDurationChart() {
      if (!this.$refs.durationChart || !this.chartData) return
      
      if (!this.durationChart) {
        this.durationChart = echarts.init(this.$refs.durationChart)
      }

      const option = {
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          borderColor: '#ddd',
          borderWidth: 1,
          textStyle: { color: '#333' },
          formatter: '{b}<br/>睡眠时长: {c} 小时'
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          top: '10%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: this.chartData.dates,
          axisLine: { lineStyle: { color: '#ddd' } },
          axisLabel: { color: '#666', rotate: 30 }
        },
        yAxis: {
          type: 'value',
          axisLine: { lineStyle: { color: '#ddd' } },
          axisLabel: { color: '#666', formatter: '{value}h' },
          splitLine: { lineStyle: { type: 'dashed' } }
        },
        series: [{
          name: '睡眠时长',
          data: this.chartData.durations,
          type: 'bar',
          barWidth: '50%',
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#667eea' },
              { offset: 1, color: '#764ba2' }
            ]),
            borderRadius: [4, 4, 0, 0]
          }
        }]
      }

      this.durationChart.setOption(option)
    },

    renderStructureChart() {
      if (!this.$refs.structureChart || !this.chartData) return
      
      if (!this.structureChart) {
        this.structureChart = echarts.init(this.$refs.structureChart)
      }

      const option = {
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          borderColor: '#ddd',
          borderWidth: 1,
          textStyle: { color: '#333' },
          formatter: (params) => {
            let result = params[0].axisValue + '<br/>'
            params.forEach(item => {
              result += `${item.marker} ${item.seriesName}: ${(item.value * 100).toFixed(1)}%<br/>`
            })
            return result
          }
        },
        legend: {
          data: ['深睡眠', 'REM睡眠', '浅睡眠'],
          top: 0
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          top: '15%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: this.chartData.dates,
          axisLine: { lineStyle: { color: '#ddd' } },
          axisLabel: { color: '#666', rotate: 30 }
        },
        yAxis: {
          type: 'value',
          max: 1,
          axisLine: { lineStyle: { color: '#ddd' } },
          axisLabel: { 
            color: '#666',
            formatter: (value) => (value * 100) + '%'
          },
          splitLine: { lineStyle: { type: 'dashed' } }
        },
        series: [
          {
            name: '深睡眠',
            type: 'bar',
            stack: 'total',
            data: this.chartData.deep_ratios,
            itemStyle: { color: '#4c51bf' }
          },
          {
            name: 'REM睡眠',
            type: 'bar',
            stack: 'total',
            data: this.chartData.rem_ratios,
            itemStyle: { color: '#805ad5' }
          },
          {
            name: '浅睡眠',
            type: 'bar',
            stack: 'total',
            data: this.chartData.light_ratios,
            itemStyle: { color: '#9f7aea' }
          }
        ]
      }

      this.structureChart.setOption(option)
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
.trends-container {
  background: white;
  border-radius: 20px;
  padding: 2rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
}

.trends-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.trends-header h2 {
  font-size: 1.5rem;
  color: #333;
  margin: 0;
}

.period-selector {
  display: flex;
  gap: 0.5rem;
}

.period-selector button {
  padding: 0.5rem 1rem;
  border: 2px solid #ddd;
  background: white;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 0.9rem;
  font-weight: 500;
}

.period-selector button.active {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border-color: #667eea;
}

.period-selector button:hover:not(.active) {
  border-color: #667eea;
  background: #f8f9ff;
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

/* 汇总卡片 */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem;
  background: #f8fafc;
  border-radius: 12px;
  transition: transform 0.3s;
}

.summary-card:hover {
  transform: translateY(-3px);
}

.summary-icon {
  font-size: 2rem;
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.summary-label {
  font-size: 0.85rem;
  color: #666;
  margin-bottom: 0.25rem;
}

.summary-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #333;
}

.summary-value.excellent { color: #48bb78; }
.summary-value.good { color: #667eea; }
.summary-value.average { color: #ed8936; }
.summary-value.poor { color: #f56565; }

/* 图表网格 */
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.chart-card {
  background: #f8fafc;
  border-radius: 15px;
  padding: 1.5rem;
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.chart-card h3 {
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.1rem;
}

/* 平均睡眠结构 */
.avg-structure-card {
  background: #f8fafc;
  border-radius: 15px;
  padding: 1.5rem;
}

.avg-structure-card h3 {
  margin-bottom: 1.5rem;
  color: #333;
  font-size: 1.1rem;
}

.structure-bars {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.structure-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.bar-label {
  width: 80px;
  font-size: 0.9rem;
  color: #666;
}

.bar-container {
  flex: 1;
  height: 24px;
  background: #e0e0e0;
  border-radius: 12px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 12px;
  transition: width 0.5s ease;
}

.bar-fill.deep { background: linear-gradient(90deg, #4c51bf, #667eea); }
.bar-fill.rem { background: linear-gradient(90deg, #805ad5, #9f7aea); }
.bar-fill.light { background: linear-gradient(90deg, #9f7aea, #b794f4); }
.bar-fill.wake { background: linear-gradient(90deg, #ed8936, #f6ad55); }

.bar-value {
  width: 60px;
  text-align: right;
  font-size: 0.9rem;
  font-weight: 600;
  color: #333;
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
@media (max-width: 900px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
  
  .trends-header {
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }
}

@media (max-width: 600px) {
  .trends-container {
    padding: 1.25rem;
  }
  
  .summary-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
