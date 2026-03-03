<template>
  <div class="dashboard">
    <div class="header">
      <h1>我的睡眠记录</h1>
      <button @click="$router.push('/analysis')" class="upload-btn">
        + 上传新文件
      </button>
    </div>

    <div class="records-grid">
      <div 
        v-for="record in records" 
        :key="record.id"
        class="record-card"
        @click="viewDetail(record.id)"
      >
        <div class="record-header">
          <h3>{{ record.file_name }}</h3>
          <span class="score" :class="getScoreClass(record.quality_score)">
            {{ record.quality_score }}分
          </span>
        </div>
        <p class="record-date">{{ formatDate(record.upload_time) }}</p>
        <div class="record-stats">
          <span>深睡: {{ (record.deep_ratio * 100).toFixed(0) }}%</span>
          <span>REM: {{ (record.rem_ratio * 100).toFixed(0) }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from '@/utils/axios'

export default {
  data() {
    return {
      records: []
    }
  },
  async mounted() {
    const res = await axios.get('/api/user/records')
    this.records = res.data.records
  },
  methods: {
    viewDetail(id) {
      this.$router.push(`/record/${id}`)
    },
    getScoreClass(score) {
      if (score >= 80) return 'excellent'
      if (score >= 60) return 'good'
      return 'poor'
    },
    formatDate(date) {
      return new Date(date).toLocaleDateString('zh-CN')
    }
  }
}
</script>

<style scoped>
.dashboard {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.upload-btn {
  padding: 0.75rem 1.5rem;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
}

.records-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.record-card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  cursor: pointer;
  transition: transform 0.3s, box-shadow 0.3s;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.record-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 5px 20px rgba(0,0,0,0.15);
}

.record-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.score {
  font-size: 1.5rem;
  font-weight: bold;
  padding: 0.25rem 0.75rem;
  border-radius: 8px;
}

.score.excellent { color: #48bb78; background: #f0fff4; }
.score.good { color: #ed8936; background: #fffaf0; }
.score.poor { color: #f56565; background: #fff5f5; }

.record-date {
  color: #666;
  font-size: 0.9rem;
  margin-bottom: 1rem;
}

.record-stats {
  display: flex;
  gap: 1rem;
  font-size: 0.9rem;
  color: #555;
}
</style>
