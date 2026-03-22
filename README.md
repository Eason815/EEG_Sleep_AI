# 基于脑电信号的睡眠质量评估系统


## 目标

1. 使用公开数据集实现基于机器学习方法的脑电睡眠分期基础算法
2. 依据睡眠分期结果对睡眠质量进行评分
3. 依据睡眠分期结果为用户提供改善睡眼质量的建议
4. (可选)与(虚拟)智能家居联动，自动调节环境以改善睡眠

## 运行环境

### 后端运行

- Python 3.10.11 

(库见./requirements.txt)

```shell
cd backend;python main.py
```

### 前端运行

- Node 20.18.0 

- npm 10.8.2

```shell
cd frontend;npm run dev
```

### 数据库

- MYSQL 8.0.31

建库语句见(./backend/data/db_init.sql)

## 关于模型

### 类1

模型文件：
```
./backend/data/sleep_stage_v8/model021101.pth
./backend/data/sleep_stage_v8/model031401.pth
```

训练流程：1split.py -> 2process.py -> 3train.py


### 类2

模型文件：
```
./backend/data/tiny_sleepnet/tiny031901.pth
```

训练流程：1split1.py -> 2process1.py -> 3train1.py


### 类3

模型文件：
```
./backend/data/sleep_stage_v8/model031901.pth
```

训练流程：1split1.py -> 2process1.py -> 3train2.py

## 参考资料

1. sleep-edf数据集
https://www.physionet.org/content/sleep-edfx/1.0.0/

