<template>
  <div class="results-container">
    <!-- 质量评分卡片 -->
    <div class="score-card">
      <div class="score-circle">
        <svg width="160" height="160">
          <circle cx="80" cy="80" r="70" fill="none" stroke="#e0e0e0" stroke-width="12"/>
          <circle 
            cx="80" cy="80" r="70" 
            fill="none" 
            stroke="url(#gradient)" 
            stroke-width="12"
            stroke-dasharray="440"
            :stroke-dashoffset="440 - (440 * qualityScore / 100)"
            transform="rotate(-90 80 80)"
          />
          <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#667eea"/>
              <stop offset="100%" style="stop-color:#764ba2"/>
            </linearGradient>
          </defs>
        </svg>
        <div class="score-value">
          <span class="score-number">{{ qualityScore }}</span>
          <span class="score-label">睡眠质量</span>
        </div>
      </div>
      <p class="score-desc">{{ getScoreDescription(qualityScore) }}</p>
    </div>

    <!-- 图表1：完整20小时记录 -->
    <div class="chart-card">
      <h3>📊 完整记录 ({{ data?.duration_hours?.toFixed(1) || 0 }}小时)</h3>
      <div ref="chartFull" style="width: 100%; height: 300px;"></div>
    </div>

    <!-- 图表2：核心睡眠区间 -->
    <div class="chart-card">
      <h3>💤 核心睡眠区间 (~{{ sleepDurationHours.toFixed(1) }}小时)</h3>
      
      <!-- 版本切换按钮 -->
      <div class="chart-controls">
        <button 
          :class="{ active: displayMode === 'smooth' }"
          @click="switchMode('smooth')">
          ✨ 平滑模式
        </button>
        <button 
          :class="{ active: displayMode === 'raw' }"
          @click="switchMode('raw')">
          📈 原始数据
        </button>
        <!-- <button 
          :class="{ active: displayMode === 'lite' }"
          @click="switchMode('lite')">
          ⚡ 轻量模式
        </button> -->
      </div>
      
      <div ref="chartSleep" style="width: 100%; height: 400px;"></div>
    </div>

    <!-- 统计卡片 -->
    <div v-if="stats" class="stats-grid">
      <div class="stat-card wake">
        <div class="stat-icon">😴</div>
        <div class="stat-content">
          <p class="stat-label">清醒时间</p>
          <p class="stat-value">{{ (stats.W_ratio * 100).toFixed(1) }}%</p>
        </div>
      </div>
      
      <div class="stat-card rem">
        <div class="stat-icon">💭</div>
        <div class="stat-content">
          <p class="stat-label">REM 睡眠</p>
          <p class="stat-value">{{ (stats.REM_ratio * 100).toFixed(1) }}%</p>
        </div>
      </div>
      
      <div class="stat-card light">
        <div class="stat-icon">🌙</div>
        <div class="stat-content">
          <p class="stat-label">浅睡眠</p>
          <p class="stat-value">{{ (stats.Light_ratio * 100).toFixed(1) }}%</p>
        </div>
      </div>
      
      <div class="stat-card deep">
        <div class="stat-icon">⭐</div>
        <div class="stat-content">
          <p class="stat-label">深睡眠</p>
          <p class="stat-value">{{ (stats.Deep_ratio * 100).toFixed(1) }}%</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts'

export default {
  name: 'Hypnogram',
  props: {
    data: {
      type: Object,
      default: null
    }
  },
  data() {
    return {
      chartFull: null,
      chartSleep: null,
      displayMode: 'smooth', // 'smooth' | 'raw' | 'lite'
      stats: null,
      qualityScore: 0
    }
  },
  computed: {
    sleepDurationHours() {
      if (!this.data) return 0
      const epochs = this.data.sleep_offset_epoch - this.data.sleep_onset_epoch
      return epochs * 0.5 / 60
    },
    // 计算核心睡眠区间的统计数据
    sleepStats() {
      if (!this.data || !this.data.sleep_hypnogram_raw) return null
      
      const hypnogram = this.data.sleep_hypnogram_raw
      const total = hypnogram.length
      
      return {
        W_ratio: hypnogram.filter(x => x === 0).length / total,
        REM_ratio: hypnogram.filter(x => x === 1).length / total,
        Light_ratio: hypnogram.filter(x => x === 2).length / total,
        Deep_ratio: hypnogram.filter(x => x === 3).length / total
      }
    }
  },
  watch: {
    data: {
      handler(newData) {
        if (newData) {
          // 使用核心睡眠区间的统计数据
          this.stats = this.sleepStats
          this.qualityScore = newData.quality_score
          this.$nextTick(() => {
            this.renderFullChart(newData)
            this.renderSleepChart(newData)
          })
        }
      },
      deep: true
    }
  },
  mounted() {
    // 延迟初始化，确保DOM完全准备好
    this.$nextTick(() => {
      if (this.$refs.chartFull && this.$refs.chartSleep) {
        this.chartFull = echarts.init(this.$refs.chartFull)
        this.chartSleep = echarts.init(this.$refs.chartSleep)
        console.log('图表初始化完成')
        
        // 如果已有数据，立即渲染
        if (this.data) {
          this.stats = this.sleepStats
          this.qualityScore = this.data.quality_score
          this.renderFullChart(this.data)
          this.renderSleepChart(this.data)
        }
      }
    })
    
    window.addEventListener('resize', () => {
      this.chartFull?.resize()
      this.chartSleep?.resize()
    })
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.handleResize)
    this.chartFull?.dispose()
    this.chartSleep?.dispose()
  },
  methods: {
    getScoreDescription(score) {
      if (score >= 90) return '优秀！睡眠质量非常好'
      if (score >= 75) return '良好，建议保持规律作息'
      if (score >= 60) return '一般，可以改善睡眠环境'
      return '较差，建议咨询专业医生'
    },
    
    switchMode(mode) {
      this.displayMode = mode
      this.renderSleepChart(this.data)
    },
    
    renderFullChart(data) {
      if (!this.chartFull) {
        console.error('chartFull 未初始化')
        return
      }
      
      console.log('渲染完整图表，数据点数:', data.hypnogram_full?.length)
      const stageNames = ['清醒', 'REM', '浅睡', '深睡']
      
      this.chartFull.setOption({
        title: {
          text: '完整睡眠记录',
          left: 'center',
          textStyle: {
            fontSize: 16,
            fontWeight: 600
          }
        },
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          borderColor: '#ddd',
          borderWidth: 1,
          textStyle: { color: '#333' },
          formatter: (params) => {
            const idx = params[0].dataIndex
            const stage = data.hypnogram_full[idx]
            const time = this.getTimeLabel(idx, data.recording_start_time)
            return `<b>时间:</b> ${time}<br/><b>阶段:</b> ${stageNames[stage]}`
          }
        },
        grid: {
          left: '5%',
          right: '5%',
          bottom: '10%',
          top: '15%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: data.hypnogram_full.map((_, i) => {
            if (i % 120 === 0) {
              return this.getTimeLabel(i, data.recording_start_time)
            }
            return ''
          }),
          axisLine: { lineStyle: { color: '#ddd' } },
          axisTick: { show: false }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 3,
          interval: 1,
          inverse: true,  // 倒转Y轴
          axisLabel: {
            formatter: (value) => stageNames[value]
          },
          axisLine: { lineStyle: { color: '#ddd' } },
          splitLine: { lineStyle: { type: 'dashed' } }
        },
        series: [{
          data: data.hypnogram_full,
          type: 'line',
          step: 'end',
          sampling: 'lttb',
          lineStyle: {
            width: 2,
            color: '#667eea'
          },
          areaStyle: {
            color: 'rgba(102, 126, 234, 0.2)'
          }
        }]
      })
    },
    
    renderSleepChart(data) {
      if (!this.chartSleep) {
        console.error('chartSleep 未初始化')
        return
      }
      
      const stageNames = ['清醒', 'REM', '浅睡', '深睡']
      
      // 根据模式选择数据
      let chartData
      let timeStep
      switch(this.displayMode) {
        case 'smooth':
          chartData = data.sleep_hypnogram_smooth
          timeStep = 0.5
          break
        case 'lite':
          chartData = data.sleep_hypnogram_lite
          timeStep = 2.0 // 2分钟
          break
        default:
          chartData = data.sleep_hypnogram_raw
          timeStep = 0.5
      }
      
      console.log('渲染核心睡眠图表，模式:', this.displayMode, '数据点数:', chartData?.length)
      
      this.chartSleep.setOption({
        title: {
          text: `核心睡眠区间 (${this.displayMode === 'smooth' ? '平滑' : this.displayMode === 'lite' ? '轻量' : '原始'})`,
          left: 'center',
          textStyle: {
            fontSize: 16,
            fontWeight: 600
          }
        },
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          borderColor: '#ddd',
          borderWidth: 1,
          textStyle: { color: '#333' },
          formatter: (params) => {
            const idx = params[0].dataIndex
            const stage = chartData[idx]
            const actualIdx = data.sleep_onset_epoch + (this.displayMode === 'lite' ? idx * 4 : idx)
            const time = this.getTimeLabel(actualIdx, data.recording_start_time)
            return `<b>时间:</b> ${time}<br/><b>阶段:</b> ${stageNames[stage]}`
          }
        },
        grid: {
          left: '5%',
          right: '5%',
          bottom: '10%',
          top: '15%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: chartData.map((_, i) => {
            const actualIdx = data.sleep_onset_epoch + (this.displayMode === 'lite' ? i * 4 : i)
            if (actualIdx % 60 === 0) {
              return this.getTimeLabel(actualIdx, data.recording_start_time)
            }
            return ''
          }),
          axisLine: { lineStyle: { color: '#ddd' } },
          axisTick: { show: false }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 3,
          interval: 1,
          inverse: true,  // 倒转Y轴
          axisLabel: {
            formatter: (value) => stageNames[value]
          },
          axisLine: { lineStyle: { color: '#ddd' } },
          splitLine: { lineStyle: { type: 'dashed' } }
        },
        series: [{
          data: chartData,
          type: 'line',
          step: 'end',
          smooth: false,
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
              { offset: 1, color: 'rgba(118, 75, 162, 0.1)' }
            ])
          }
        }]
      })
    },
    
    getTimeLabel(epochIndex, startTime) {
      const minutes = epochIndex * 0.5
      if (!startTime) {
        const hours = Math.floor(minutes / 60)
        const mins = Math.floor(minutes % 60)
        return `${hours}h${mins}m`
      }
      
      try {
        // 直接解析ISO时间字符串，不做地区转换
        const timeMatch = startTime.match(/T(\d{2}):(\d{2}):(\d{2})/)
        if (timeMatch) {
          const startHour = parseInt(timeMatch[1])
          const startMinute = parseInt(timeMatch[2])
          
          // 计算当前时间
          const totalMinutes = startHour * 60 + startMinute + minutes
          const currentHour = Math.floor(totalMinutes / 60) % 24
          const currentMinute = Math.floor(totalMinutes % 60)
          
          return `${String(currentHour).padStart(2, '0')}:${String(currentMinute).padStart(2, '0')}`
        }
        
        // 备用方案
        const hours = Math.floor(minutes / 60)
        const mins = Math.floor(minutes % 60)
        return `${hours}h${mins}m`
      } catch (e) {
        const hours = Math.floor(minutes / 60)
        const mins = Math.floor(minutes % 60)
        return `${hours}h${mins}m`
      }
    }
  }
}
</script>

<style scoped>
.results-container {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 1.5rem;
  margin-top: 2rem;
}

.score-card {
  background: white;
  border-radius: 20px;
  padding: 2rem;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}

.score-circle {
  position: relative;
  margin: 0 auto 1.5rem;
  width: 160px;
  height: 160px;
}

.score-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.score-number {
  display: block;
  font-size: 3rem;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  background-clip: text; 
  -webkit-text-fill-color: transparent;
}

.score-label {
  display: block;
  font-size: 0.9rem;
  color: #666;
  margin-top: 0.25rem;
}

.score-desc {
  color: #666;
  font-size: 0.95rem;
  line-height: 1.5;
}

.chart-card {
  background: white;
  border-radius: 20px;
  padding: 2rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  grid-column: 1 / -1;
}

.chart-card h3 {
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.25rem;
}

.chart-controls {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  justify-content: center;
}

.chart-controls button {
  padding: 0.5rem 1rem;
  border: 2px solid #ddd;
  background: white;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 0.9rem;
  font-weight: 500;
}

.chart-controls button.active {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border-color: #667eea;
}

.chart-controls button:hover:not(.active) {
  border-color: #667eea;
  background: #f8f9ff;
}

.stats-grid {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
}

.stat-card {
  background: white;
  border-radius: 15px;
  padding: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  box-shadow: 0 4px 15px rgba(0,0,0,0.08);
  transition: transform 0.3s;
}

.stat-card:hover {
  transform: translateY(-5px);
}

.stat-icon {
  font-size: 2.5rem;
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: #f5f5f5;
}

.wake .stat-icon { background: #fff5f5; }
.rem .stat-icon { background: #fffaf0; }
.light .stat-icon { background: #f0fff4; }
.deep .stat-icon { background: #eff6ff; }

.stat-label {
  font-size: 0.9rem;
  color: #666;
  margin-bottom: 0.25rem;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: #333;
}

@media (max-width: 768px) {
  .results-container {
    grid-template-columns: 1fr;
  }
}
</style>
