<template>
  <div class="results-container">
    <!-- 顶部卡片行：评分 + 详细指标 + 睡眠建议 -->
    <div class="top-cards-row">
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

      <!-- 详细指标卡片 -->
      <div class="metrics-card" v-if="data?.sub_scores && data?.metrics">
        <h3>📊 详细指标</h3>
        <div class="metrics-content">
          <div class="metrics-column">
            <h4>维度得分</h4>
            <div class="metric-item">
              <span class="metric-label">睡眠效率</span>
              <span class="metric-value">{{ data.sub_scores.efficiency.toFixed(1) }}分</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">睡眠结构</span>
              <span class="metric-value">{{ data.sub_scores.architecture.toFixed(1) }}分</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">连续性</span>
              <span class="metric-value">{{ data.sub_scores.continuity.toFixed(1) }}分</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">时间特征</span>
              <span class="metric-value">{{ data.sub_scores.timing.toFixed(1) }}分</span>
            </div>
          </div>
          <div class="metrics-divider"></div>
          <div class="metrics-column">
            <h4>详细数据</h4>
            <div class="metric-item">
              <span class="metric-label">入睡延迟</span>
              <span class="metric-value">{{ data.metrics.sleep_latency_min.toFixed(0) }}分钟</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">觉醒次数</span>
              <span class="metric-value">{{ data.metrics.num_awakenings }}次</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">睡眠周期</span>
              <span class="metric-value">{{ data.metrics.num_cycles }}个</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">碎片化指数</span>
              <span class="metric-value">{{ data.metrics.fragmentation_index.toFixed(1) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 睡眠建议卡片 -->
      <div class="recommendations-card" v-if="data?.recommendations?.length">
        <h3>💡 睡眠建议</h3>
        <div class="recommendations-content">
          <div class="recommendations-grid">
            <div 
              v-for="(rec, index) in data.recommendations" 
              :key="index" 
              class="recommendation-item"
            >
              {{ rec }}
            </div>
          </div>
        </div>
      </div>
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
    },
    // 计算入睡时间（核心睡眠起点 + 1200秒 = +40个epoch，因为1个epoch=30秒）
    sleepOnsetTime() {
      if (!this.data) return ''
      const epochIndex = this.data.sleep_onset_epoch + 40
      return this.getTimeLabel(epochIndex, this.data.recording_start_time)
    },
    // 计算醒来时间（核心睡眠终点 - 1200秒 = -40个epoch，因为1个epoch=30秒）
    wakeUpTime() {
      if (!this.data) return ''
      const epochIndex = this.data.sleep_offset_epoch - 40
      return this.getTimeLabel(epochIndex, this.data.recording_start_time)
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
      
      // 动态计算标签间隔，确保显示合理数量的标签
      const totalPoints = data.hypnogram_full.length
      const targetLabels = 8 // 目标显示约8个标签
      const labelInterval = Math.max(1, Math.floor(totalPoints / targetLabels))
      
      // 生成时间标签数组，避免末尾重影
      const timeLabels = data.hypnogram_full.map((_, i) => {
        // 检查是否是最后一个点
        if (i === totalPoints - 1) {
          // 如果最后一个点距离前一个标签太近（小于间隔的50%），则不显示
          const lastLabelIndex = Math.floor((totalPoints - 1) / labelInterval) * labelInterval
          if (totalPoints - 1 - lastLabelIndex < labelInterval * 0.5) {
            return ''
          }
          return this.getTimeLabel(i, data.recording_start_time)
        }
        // 按间隔显示标签
        if (i % labelInterval === 0) {
          return this.getTimeLabel(i, data.recording_start_time)
        }
        return ''
      })
      
      console.log('完整图表标签间隔:', labelInterval, '总标签数:', timeLabels.filter(l => l).length)
      
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
          data: timeLabels,
          axisLine: { lineStyle: { color: '#ddd' } },
          axisTick: { show: false },
          axisLabel: {
            interval: 0, // 显示所有非空标签
            rotate: 0,
            fontSize: 11,
            color: '#666'
          }
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
      
      // 动态计算标签间隔（改为8个标签以提升性能）
      const totalPoints = chartData.length
      const targetLabels = 8 // 目标显示约8个标签
      const labelInterval = Math.max(1, Math.floor(totalPoints / targetLabels))
      
      // 生成时间标签数组，避免末尾重影
      const timeLabels = chartData.map((_, i) => {
        // 检查是否是最后一个点
        if (i === totalPoints - 1) {
          // 如果最后一个点距离前一个标签太近（小于间隔的50%），则不显示
          const lastLabelIndex = Math.floor((totalPoints - 1) / labelInterval) * labelInterval
          if (totalPoints - 1 - lastLabelIndex < labelInterval * 0.5) {
            return ''
          }
          const actualIdx = data.sleep_onset_epoch + (this.displayMode === 'lite' ? i * 4 : i)
          return this.getTimeLabel(actualIdx, data.recording_start_time)
        }
        // 按间隔显示标签
        if (i % labelInterval === 0) {
          const actualIdx = data.sleep_onset_epoch + (this.displayMode === 'lite' ? i * 4 : i)
          return this.getTimeLabel(actualIdx, data.recording_start_time)
        }
        return ''
      })
      
      console.log('核心睡眠图表标签间隔:', labelInterval, '总标签数:', timeLabels.filter(l => l).length)
      
      // 计算入睡和醒来时间在图表中的位置
      // 注意：这里的索引是相对于chartData数组的，不是epoch数
      const sleepOnsetIndex = 40 // 入睡时间：起点后40个epoch（1200秒 ÷ 30秒/epoch = 40）
      const wakeUpIndex = (data.sleep_offset_epoch - data.sleep_onset_epoch) - 40 // 醒来时间：终点前40个epoch
      
      // 确保索引在有效范围内
      const validSleepOnsetIndex = Math.min(Math.max(0, sleepOnsetIndex), totalPoints - 1)
      const validWakeUpIndex = Math.min(Math.max(0, wakeUpIndex), totalPoints - 1)
      
      console.log('入睡时间索引:', validSleepOnsetIndex, '醒来时间索引:', validWakeUpIndex, '总数据点:', totalPoints)
      
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
          data: timeLabels,
          axisLine: { lineStyle: { color: '#ddd' } },
          axisTick: { show: false },
          axisLabel: {
            interval: 0, // 显示所有非空标签
            rotate: 0,
            fontSize: 11,
            color: '#666'
          }
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
          },
          markLine: {
            symbol: ['none', 'none'],
            label: {
              show: true,
              position: 'end',
              formatter: '{b}',
              fontSize: 11,
              color: '#333',
              backgroundColor: 'rgba(255, 255, 255, 0.9)',
              padding: [4, 8],
              borderRadius: 4
            },
            data: [
              {
                name: `😴 入睡 ${this.sleepOnsetTime}`,
                xAxis: validSleepOnsetIndex,
                lineStyle: {
                  color: '#48bb78',
                  width: 2,
                  type: 'dashed'
                }
              },
              {
                name: `😊 醒来 ${this.wakeUpTime}`,
                xAxis: validWakeUpIndex,
                lineStyle: {
                  color: '#ed8936',
                  width: 2,
                  type: 'dashed'
                }
              }
            ]
          }
        }]
      })
    },
    
    getTimeLabel(epochIndex, startTime) {
      const minutes = epochIndex * 0.5
      
      // 如果没有提供开始时间，使用相对时间格式
      if (!startTime) {
        const hours = Math.floor(minutes / 60)
        const mins = Math.floor(minutes % 60)
        return `${hours}h${mins}m`
      }
      
      try {
        // 尝试多种时间格式解析
        let startHour, startMinute
        
        // 格式1: ISO 8601 格式 (YYYY-MM-DDTHH:MM:SS)
        let timeMatch = startTime.match(/T(\d{2}):(\d{2}):(\d{2})/)
        if (timeMatch) {
          startHour = parseInt(timeMatch[1])
          startMinute = parseInt(timeMatch[2])
        } else {
          // 格式2: 简单时间格式 (HH:MM:SS 或 HH:MM)
          timeMatch = startTime.match(/(\d{1,2}):(\d{2})/)
          if (timeMatch) {
            startHour = parseInt(timeMatch[1])
            startMinute = parseInt(timeMatch[2])
          } else {
            // 格式3: 尝试使用 Date 对象解析
            const date = new Date(startTime)
            if (!isNaN(date.getTime())) {
              startHour = date.getHours()
              startMinute = date.getMinutes()
            } else {
              // 无法解析，使用相对时间
              console.warn('无法解析时间格式:', startTime)
              const hours = Math.floor(minutes / 60)
              const mins = Math.floor(minutes % 60)
              return `${hours}h${mins}m`
            }
          }
        }
        
        // 计算当前时间点
        const totalMinutes = startHour * 60 + startMinute + minutes
        const currentHour = Math.floor(totalMinutes / 60) % 24
        const currentMinute = Math.floor(totalMinutes % 60)
        
        return `${String(currentHour).padStart(2, '0')}:${String(currentMinute).padStart(2, '0')}`
        
      } catch (e) {
        console.error('时间标签生成错误:', e, 'startTime:', startTime)
        // 出错时使用相对时间格式
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
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  margin-top: 2rem;
}

/* 顶部卡片行：三个卡片并排 */
.top-cards-row {
  display: grid;
  grid-template-columns: 280px 1fr 1fr;
  gap: 1.5rem;
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

/* 详细指标卡片 */
.metrics-card {
  background: white;
  border-radius: 20px;
  padding: 1.5rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}

.metrics-card h3 {
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.1rem;
  text-align: center;
}

.metrics-content {
  display: flex;
  gap: 1rem;
}

.metrics-column {
  flex: 1;
}

.metrics-column h4 {
  font-size: 0.85rem;
  color: #888;
  margin-bottom: 0.75rem;
  font-weight: 500;
}

.metrics-divider {
  width: 1px;
  background: #e0e0e0;
  margin: 0 0.5rem;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0;
  font-size: 0.9rem;
}

.metric-label {
  color: #666;
}

.metric-value {
  color: #333;
  font-weight: 600;
}

/* 睡眠建议卡片 */
.recommendations-card {
  background: white;
  border-radius: 20px;
  padding: 1.5rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}

.recommendations-card h3 {
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.1rem;
  text-align: center;
}

.recommendations-content {
  max-height: 200px;
  overflow-y: auto;
}

.recommendations-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.recommendation-item {
  font-size: 0.85rem;
  color: #555;
  line-height: 1.5;
  padding: 0.5rem;
  background: #f8f9ff;
  border-radius: 8px;
  white-space: pre-line;
}

@media (max-width: 1200px) {
  .top-cards-row {
    grid-template-columns: 1fr;
  }
  
  .recommendations-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .results-container {
    gap: 1rem;
  }
  
  .top-cards-row {
    gap: 1rem;
  }
  
  .metrics-content {
    flex-direction: column;
  }
  
  .metrics-divider {
    display: none;
  }
}
</style>
