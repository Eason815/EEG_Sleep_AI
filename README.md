# EEG Sleep AI

> 基于单通道 EEG 脑电信号的睡眠分期、睡眠质量评估与调控建议系统。项目使用 Sleep-EDF 数据集，结合 PyTorch、FastAPI 与 Vue 3，实现 EDF 文件上传、睡眠分期推理、质量评分、趋势分析与模拟调控策略生成。

<p align="center">
  <img src="./cover.png" alt="EEG Sleep AI cover" width="100%" />
</p>

## 项目目标

1. 使用公开数据集实现基于机器学习方法的脑电睡眠分期基础算法
2. 依据睡眠分期结果对睡眠质量进行评分
3. 依据睡眠分期结果为用户提供改善睡眼质量的建议
4. (可选)与(虚拟)智能家居联动，自动调节环境以改善睡眠

## 功能模块

### 1. 脑电睡眠分期

- 支持上传标准 `.edf` 睡眠文件
- 基于单通道 EEG `Fpz-Cz` 进行自动分析
- 当前支持多种模型并可在前端切换推理：
  - `SleepStageV8`
  - `TinySleepNet`
- 训练时以 5 类睡眠阶段为基础：`W / N1 / N2 / N3 / REM`
- 展示与评分阶段进一步融合为 4 类结果：`W / REM / Light / Deep`

### 2. 睡眠质量评分

系统在睡眠分期基础上进一步计算：

- 睡眠效率 `Sleep Efficiency`
- 入睡潜伏期 `Sleep Latency`
- 入睡后觉醒时间 `WASO`
- REM 潜伏期 `REM Latency`
- 睡眠周期数
- 觉醒次数
- 睡眠碎片化指数
- 深睡、浅睡、REM、清醒占比

最终将指标汇总为四个维度得分：

- 睡眠效率
- 睡眠结构
- 睡眠连续性
- 时间特征

并生成 0-100 的综合睡眠质量评分与对应建议。

### 3. 可视化分析报告

前端提供完整的睡眠报告展示能力，包括：

- 完整睡眠记录图
- 核心睡眠区间图
- 平滑 / 原始模式切换
- 睡眠质量评分卡片
- 睡眠结构占比统计
- 个性化睡眠建议

### 4. 用户系统与长期跟踪

- 用户注册 / 登录
- 历史分析记录保存
- 趋势分析（最近 7 天 / 30 天 / 全部）
- 睡眠质量、时长与结构变化可视化
- 用户目标设置（目标睡眠时长、目标深睡比例、目标 REM 比例）

### 5. 调控中心

系统会结合最近一次分析结果，生成一套“模拟智能家居调控方案”，包括：

- 问题识别
- 推荐场景生成
- 温度 / 灯光 / 窗帘 / 白噪音 / 加湿器目标状态
- 自动化时间线
- 模拟执行日志

该部分目前为演示型功能，不依赖真实硬件设备。



## 技术栈

### 后端

- FastAPI
- SQLAlchemy
- MySQL
- PyTorch
- MNE
- NumPy / Scikit-learn

### 前端

- Vue 3
- Vite
- ECharts

## 项目结构

```text
EEG_Sleep_AI/
├─ backend/                    # FastAPI 后端
│  ├─ main.py                  # 服务入口
│  ├─ routers/                 # 鉴权、分析、历史、趋势、调控、用户接口
│  ├─ services/                # 睡眠分析、评分、调控策略
│  ├─ models/                  # 推理模型、模型管理器、预测器
│  ├─ deps/                    # 数据库与鉴权依赖
│  ├─ entity/                  # 数据表与响应模型
│  └─ data/                    # 数据库脚本、模型权重
├─ frontend/                   # Vue 3 前端
│  └─ src/components/          # 上传、结果、历史、趋势、调控、设置等组件
├─ 1split.py                   # 基础划分脚本
├─ 2process.py                 # 基础预处理脚本
├─ 3train.py                   # 基础 SleepStageV8 训练脚本
├─ 1split1.py                  # 按受试者划分 10 折交叉验证清单
├─ 2process1.py                # TinySleepNet / 论文协议预处理缓存生成
├─ 3train1.py                  # TinySleepNet 训练脚本
├─ 3train2.py                  # SleepStageV8 交叉验证训练脚本
├─ cover.png                   # GitHub 首页封面图
├─ evaluate_sleep_cropping.py  # 睡眠区间裁剪评估辅助脚本
└─ vexper/                     # 训练与实验 notebook
```

## 运行环境

### 推荐环境

- Python `3.10.11`
- Node.js `20.x`
- npm `10.x`
- MySQL `8.0.31`
- CUDA 环境（可选，训练和推理时建议使用）

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Eason815/EEG_Sleep_AI.git
cd EEG_Sleep_AI
```

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 配置数据库

默认数据库连接写在：

```text
backend/deps/database.py
```

当前示例配置为：

```python
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:123456@localhost/sleep_db"
```

随后执行建库脚本：

```text
backend/data/db_init.sql
```

### 4. 启动后端

```bash
cd backend
python main.py
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端启动后即可在浏览器中访问页面并进行登录、上传和分析。

## 数据与模型说明

### 数据集

本项目主要使用公开数据集：

- Sleep-EDF Expanded  
  [https://www.physionet.org/content/sleep-edfx/1.0.0/](https://www.physionet.org/content/sleep-edfx/1.0.0/)

默认脚本假定原始数据位于：

```text
./sleep-edf/sleep-cassette
```

### 模型权重

仓库内已经包含部分模型权重示例：

```text
./backend/data/sleep_stage_v8/model021101.pth
./backend/data/sleep_stage_v8/model031401.pth
./backend/data/sleep_stage_v8/model031901.pth
./backend/data/tiny_sleepnet/tiny031901.pth
```

后端启动时会自动扫描 `backend/data/` 下的模型文件，并在前端展示可选模型列表。

## 训练流程

### 方案一：基础训练流程

适用于较直观的 train / val / test 划分方式：

```text
1split.py -> 2process.py -> 3train.py
```

对应：

- `1split.py`：将 Sleep-EDF 原始文件按病人随机划分为训练、验证、测试集
- `2process.py`：完成裁剪、重采样、滤波、按 30 秒切 epoch、标签映射和缓存保存
- `3train.py`：训练基于上下文窗口的 `SleepStageV8`

### 方案二：论文协议 / 交叉验证流程

更适合严谨实验设置：

```text
1split1.py -> 2process1.py -> 3train1.py / 3train2.py
```

对应：

- `1split1.py`：按受试者构建 10 折交叉验证清单，避免同一受试者泄漏到不同集合
- `2process1.py`：按论文风格生成全局缓存，并提取睡眠相关片段
- `3train1.py`：训练 `TinySleepNet`
- `3train2.py`：训练 `SleepStageV8` 并进行交叉验证评估

## 后端主要接口

系统核心接口包括：

- `GET /api/health`：健康检查
- `GET /api/models`：获取可用模型列表
- `POST /api/analyze`：上传 EDF 并执行睡眠分析
- `GET /api/history`：获取历史记录
- `GET /api/trends`：获取趋势分析
- `GET /api/regulation/plan`：获取调控方案
- `GET /api/user/profile`：获取用户信息
- `PUT /api/user/settings`：更新用户目标设置



## 参考资料

1. Sleep-EDF Expanded 
https://www.physionet.org/content/sleep-edfx/1.0.0/

1. `[1]` 何静文等，《中国睡眠研究报告2023》解读: [期刊HTML](https://html.rhhz.net/dejydxxb/html/2023/11/20230211.htm)
2. `[2]` AASM Manual: [AASM 官方页](https://isr.aasm.org/helpv6/TheAASMManualfortheScoringofSlee.html)
3. `[3]` 金峥，贾克斌，自动睡眠分期算法综述: [北京工业大学学报期刊页](https://journal.bjut.edu.cn/bjgydxxb/article/doi/10.11936/bjutxb2024040035)
4. `[4]` Goldberger et al., PhysioBank/PhysioNet: [PubMed](https://pubmed.ncbi.nlm.nih.gov/10851218/)
5. `[5]` Supratak, Guo, TinySleepNet: [PubMed](https://pubmed.ncbi.nlm.nih.gov/33018069/)
6. `[6]` 张所滨，徐周波，B/S架构办公自动化: [期刊页](https://cjournal.hep.com.cn/1673-808X/CN/1160175292506628707)
7. `[7]` Guo et al., FlexSleepTransformer: [Scientific Reports](https://www.nature.com/articles/s41598-024-76197-0)
8. `[8]` Kemp et al., slow-wave microcontinuity of the EEG: [PubMed](https://pubmed.ncbi.nlm.nih.gov/11008419/)
9. `[9]` 钟博等，EEG数据分析技术综述: [浙江大学学报(工学版)](https://www.zjujournals.com/eng/article/2024/1008-973X/20240501.shtml)
10. `[10]` 卢伊虹等，基于CNN-BiLSTM的自动睡眠分期算法: [计算机系统应用](https://www.c-s-a.org.cn/html/2022/4/8450.htm)
11. `[11]` He et al., Deep Residual Learning for Image Recognition: [CVF Open Access PDF](https://www.cv-foundation.org/openaccess/content_cvpr_2016/papers/He_Deep_Residual_Learning_CVPR_2016_paper.pdf)
12. `[12]` Hu et al., Squeeze-and-Excitation Networks: [CVF Open Access](https://openaccess.thecvf.com/content_cvpr_2018/html/Hu_Squeeze-and-Excitation_Networks_CVPR_2018_paper.html)
13. `[13]` Yang et al., LMCSleepNet: [MDPI Sensors](https://www.mdpi.com/1424-8220/25/19/6065)
14. `[14]` Fiorillo et al., DeepSleepNet-Lite: [PubMed](https://pubmed.ncbi.nlm.nih.gov/34648450/)
15. `[15]` Sun, Zhao, ADG-SleepNet: [MDPI Symmetry](https://www.mdpi.com/2073-8994/17/9/1461)
16. `[16]` 刘贤臣等，匹兹堡睡眠质量指数的信度和效度研究: [中华精神科杂志页](https://rs.yiigle.com/CN115399202004/700801.htm)
17. `[17]` 杨丽丽等，睡眠剥夺对学习记忆的影响及机制研究进展: [期刊页](https://bmjj.cbpt.cnki.net/portal/journal/portal/client/paper/f577033cf0313d4842bb26a091ff9545)
18. `[18]` 冯攀，郑涌，睡眠剥夺影响恐惧情绪加工的认知神经机制: [心理科学进展](https://journal.psych.ac.cn/xlkxjz/CN/10.3724/SP.J.1042.2015.01579)
19. `[19]` Ohayon et al., sleep quality recommendations: [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2352721816301309)
20. `[20]` 白亚宁等，极端环境对人类睡眠的影响: [四川大学学报(医学版)](https://ykxb.scu.edu.cn/article/doi/10.12182/20240760402)
21. `[21]` 汪统岳等，光照强度和时间对褪黑素和睡眠节律的影响: [可读页面](https://www.fx361.cc/page/2022/0730/13792652.shtml)
22. `[22]` 蒋晓江等，白噪声对睡眠生理的影响及其治疗应用: [万方医学](https://med.wanfangdata.com.cn/Paper/Detail?id=PeriodicalPaper_zglcsjkx201706017)
23. `[23]` 祁凤燕，王海英，睡眠卫生护理干预对失眠患者睡眠质量的影响: [心理月刊](https://www.xlykzz.com/CN/10.19738/j.cnki.psy.2021.09.053)
