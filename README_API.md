# Storage Optimization API

| 项 | 值 |
|----|-----|
| 默认端口 | `8001` |
| OpenAPI | `http://127.0.0.1:8001/docs` |
| 健康检查 | `GET /health` → `success` / `code` / `message` |

## 启动

```bash
python -m uvicorn storage_optimization_api:app --host 127.0.0.1 --port 8001
```

## 通用响应形态

| 情况 | 结构 |
|------|------|
| 成功 | `{ "success": true, "code": "OK", "message": "…", "data": { … } }` |
| 失败 | `{ "success": false, "error": { "code", "message", "details" } }` |

---

## 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/storage-optimization/optimize` | 日前优化（全日） |
| POST | `/storage-optimization/rolling-optimize` | 滚动优化（4 小时预测窗） |
| POST | `/optimize` | 窗口优化（笔记本逻辑，1～4 点） |

---

## 1. 日前优化 `POST /storage-optimization/optimize`

### 请求体 `application/json`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `baseline_kw` | `number[]` | 是 | 基线功率（kW），正充电、负放电，长度 **24 或 96** |
| `max_charge_power_limit_kw` | `number[]` | 是 | 功率上限（kW），与 `baseline_kw` **同长度** |
| `date` | `string` | 否 | 电价日期 `yyyy-mm-dd`，有默认值 |
| `energy_threshold_kwh` | `number` | 否 | 连续段最小有效电量阈值（kWh），默认 `0.00001` |
| `initial_soc_kwh` | `number` \| `null` | 否 | 与 `energy_capacity_kwh` **须成对**提供或都省略 |
| `energy_capacity_kwh` | `number` \| `null` | 否 | 储能可用能量上限（kWh）；成对提供时做 SOC 修正 |
| `soc_min_kwh` | `number` | 否 | SOC 下限（kWh），默认 `0` |

### 成功时 `data` 主要字段

| 字段 | 说明 |
|------|------|
| `price_date` | 使用的电价日期 |
| `baseline_changed` | 基线相对裁剪/SOC 是否变化 |
| `baseline_kw_effective` | 实际参与优化的基线（kW，与入参粒度一致） |
| `summary` | `baseline` / `optimized` 内含 `charge_energy_kwh`、`discharge_energy_kwh` |
| `result_15m` | **96** 行，每行：`slot`、`time`、`price`、`baseline_power_kw`、`optimized_power_kw` |
| `soc_baseline` | 仅当成对提供 SOC 参数时出现：`initial_soc_kwh`、`soc_min_kwh`、`soc_max_kwh` |

---

## 2. 滚动优化 `POST /storage-optimization/rolling-optimize`

### 请求体 `application/json`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `baseline_kw_24` | `number[]` | 是 | 24 点小时基线（kW），正充电、负放电 |
| `max_power_limit_kw_24` | `number[]` | 是 | 24 点功率上限（kW） |
| `energy_capacity_kwh` | `number` | 是 | 容量（kWh） |
| `initial_soc_kwh` | `number` | 否 | 日初 SOC（kWh），默认 `0` |
| `soc_min_kwh` | `number` | 否 | SOC 下限（kWh），默认 `0` |
| `date` | `string` | 否 | `yyyy-mm-dd` |
| `priorActualKwBeforeAnchor` | `number[]` | 是 | 锚点**之前**各已结束整点小时的实际功率（kW），**每小时一条**；其长度会自动作为 `start_hour` 推断（长度 0..23 对应锚点 `00:00`..`23:00`） |

### 成功时 `data` 主要字段

| 字段 | 说明 |
|------|------|
| `resolved_query_time` | 实际采用的锚点时间（如 `10:00`） |
| `baseline_changed` | 基线相对裁剪/SOC 是否变化 |
| `baseline_kw_24` | 固定展示口径的 24 点基线（kW），按 `priorActualKwBeforeAnchor=[]` 等价场景计算，不随 `priorActualKwBeforeAnchor` 变化 |
| `points` | 预测窗内点：`slot`、`time`、`price`、`price_tag`、`baseline_power_kw`、`optimized_power_kw` |
| `regulation_feedback` | **第一个**相交周期的简要调控信息（见下表） |
| `regulation_feedback_cycles` | 各相交周期一条，与 `cycle_blocks` 顺序一致 |
| `warnings` | 字符串数组，有则出现（如基线 SOC 缺口提示等） |

备注：`baseline_for_regulation_kw_24` 为内部调控计算字段，不在接口响应中对外输出。

**`regulation_feedback` / `regulation_feedback_cycles` 单项结构**

| 字段 | 说明 |
|------|------|
| `cycle_mode` | `charge` 或 `discharge` |
| `cycle_end_time` | 该周期最后一个 15 分钟段结束时刻 `HH:MM` |
| `next_regulation_earliest` | 建议下次锚点不早于该时刻（优先结合可达性临界判定） |
| `reachable` | 当前周期剩余窗口是否可达目标总电量 |
| `must_run_full_power` | 是否已进入“必须连续满功率执行”临界状态 |
| `must_run_direction` | 临界执行方向：`charge` / `discharge`，非临界时为 `null` |
| `earliest_safe_next_regulation_time` | 若处于临界态，建议在该时刻前避免再次下发调控 |
| `reason` | 不可达原因（仅 `reachable=false` 时出现） |
| `remark` | 一句说明 |

---

## 3. 窗口优化 `POST /optimize`

与日前/滚动不同子应用，路径仍为根路径 **`/optimize`**。

### 请求体 `application/json`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `points` | `array` | 是 | **1～4** 条，小时**连续** |

**`points[]` 每项**

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | `string` | 日期 `YYYY-MM-DD` |
| `time` | `number` | 小时（与实现一致，0～23 连续） |
| `region_name` | `string` | 区域：`jiangnan` / `jiangbei` / `all` |
| `baseline_kw` | `number` | 基线功率（kW） |
| `energy_cap_kwh` | `number` | 能量相关容量参数（kWh） |
| `rated_power_kw` | `number` | 额定功率（kW），多点时取平均参与约束 |

### 成功响应（无统一 `success` 包装）

| 字段 | 说明 |
|------|------|
| `results` | 每点一行：日期、小时、`price`、`region_name`、`baseline_kw`、`optimized_kw`、收益等 |
| `summary` | 如 `points_in`、总收益与 `total_gain`（多点时） |

---

## 滚动常见业务错误码（节选）

`PRIOR_ACTUAL_LENGTH_MISMATCH`、`SOC_AFTER_PRIOR_OUT_OF_RANGE`、`QUERY_MARKET_PRICE_*`、`ROLLING_WINDOW_*`、`ROLLING_BLOCK_NOT_FOUND` 等，以响应中 `error.code` 为准。
