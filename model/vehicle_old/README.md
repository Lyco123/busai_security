# vehicle

`vehicle` 是当前车辆画像评分主工程，拆成两个独立入口：

- `app_weight_update.py`：按日期范围训练模型，输出 SQL 口径权重表、模型和元数据。
- `app_score_update.py`：按日期范围读取评分数据，取范围内最新一天输出解释型评分结果。

## 快速运行

```powershell
D:\Software\anaconda3\envs\VRP\python.exe .\vehicle_codex\app_weight_update.py
D:\Software\anaconda3\envs\VRP\python.exe .\vehicle_codex\app_score_update.py
```

两个入口都支持命令行覆盖：

- `--start-date`
- `--end-date`
- `--create-date`
- `--weight-month`：可选，不传时默认取 `create_date` 所在月份

## 目录结构

```text
vehicle_codex/
├─ app_weight_update.py
├─ app_score_update.py
├─ README.md
├─ docs/
├─ config/
├─ data/
├─ output/
└─ src/
```

## 输出结构

当前输出按批次建子目录：

- `output/weights/<batch_name>/`
- `output/models/<batch_name>/`
- `output/scores/<batch_name>/`
- `output/logs/<batch_name>/`

其中 `batch_name` 规则为：

- `weight_开始日期_结束日期_创建日期`
- `score_开始日期_结束日期_创建日期`
