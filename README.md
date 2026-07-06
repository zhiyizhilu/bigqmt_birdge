# QMT Bridge — QMT 大智慧 HTTP 桥接服务

> 通过 RESTful API 从外部 Python 环境调用 QMT（迅投极速策略交易系统）的数据和交易接口

---

## 目录

- [项目概述](#项目概述)
- [架构设计](#架构设计)
- [核心特性](#核心特性)
- [安装与配置](#安装与配置)
- [API 参考](#api-参考)
  - [系统接口](#1-系统接口)
  - [上下文属性查询](#2-上下文属性查询)
  - [上下文设置](#3-上下文设置)
  - [数据查询](#4-数据查询)
  - [订阅接口](#5-订阅接口)
  - [判定函数](#6-判定函数)
  - [交易接口](#7-交易接口)
  - [账户与订单查询](#8-账户与订单查询)
  - [扩展数据与引用函数](#9-扩展数据与引用函数)
  - [板块管理](#10-板块管理)
  - [兼容路由](#11-兼容路由)
- [客户端使用](#客户端使用)
- [测试套件](#测试套件)
- [注意事项](#注意事项)
- [项目结构](#项目结构)
- [故障排除](#故障排除)

---

## 项目概述

QMT Bridge 是一个轻量级的 HTTP 桥接服务，使外部 Python 程序能够通过 RESTful API 访问 QMT 大智慧内置 Python 的数据和交易能力。

**核心思路**：在 QMT 策略编辑器中运行一个 Tornado HTTP Server（`qmt_server.py`），将 QMT 内置 Python 的 API 封装为 HTTP 接口；外部程序通过 `qmt_client.py`（基于 requests）调用这些接口，实现与 QMT 的交互。

**适用场景**：
- 在 Jupyter Notebook / VS Code 等外部环境中获取 QMT 行情数据
- 通过外部程序自动化下单、撤单
- 将 QMT 数据集成到自建量化框架
- 跨进程、跨语言调用 QMT 能力

---

## 架构设计

```
┌──────────────────────────────────────────────────┐
│                QMT 大智慧策略编辑器                 │
│  ┌────────────────────────────────────────────┐  │
│  │           qmt_server.py (Tornado)          │  │
│  │                                            │  │
│  │  init(ContextInfo)                         │  │
│  │    → 创建 HTTPServer，监听 127.0.0.1:8888  │  │
│  │    → 注册路由，绑定 ContextInfo             │  │
│  │    → 启动 IOLoop                           │  │
│  │                                            │  │
│  │  handlebar(ContextInfo)                    │  │
│  │    → QMT 周期回调（保持策略运行）            │  │
│  │                                            │  │
│  │  stop(ContextInfo)                         │  │
│  │    → 停止 HTTP 服务                        │  │
│  │                                            │  │
│  │  BaseHandler.ctx()  → ContextInfo 实例      │  │
│  │  BaseHandler.acc()  → 账户 ID              │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
                        │
                   HTTP (JSON)
                        │
┌──────────────────────────────────────────────────┐
│              外部 Python 环境                      │
│  ┌────────────────────────────────────────────┐  │
│  │         qmt_client.py (requests)           │  │
│  │                                            │  │
│  │  QMTClient(base_url, token)                │  │
│  │    → buy_stock / sell_stock / passorder    │  │
│  │    → get_full_tick / get_market_data_ex    │  │
│  │    → get_holding / get_total_money         │  │
│  │    → ... 100+ API 方法                     │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

**关键设计**：
- 服务端通过 `app.ContextInfo = ContextInfo` 将 QMT 的上下文对象绑定到 Tornado Application，所有 Handler 通过 `self.ctx()` 访问
- 订阅回调通过模块级缓存变量 `_sub_tick_cache` / `_sub_quote_cache` 存储数据，客户端通过缓存查询接口轮询获取
- `handlebar` 函数为空实现，仅用于维持 QMT 策略运行周期

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **不依赖 xtquant** | 纯 HTTP 桥接，客户端只需 `requests` 库 |
| **Tornado HTTP Server** | 内嵌 QMT 策略，异步非阻塞，支持并发请求 |
| **NaN/Inf 安全序列化** | `_clean_nan()` + `safe_json_dumps()` 递归处理 NaN/Inf，避免 JSON 序列化失败 |
| **全局共享变量** | 类实例属性（非 global 变量）确保回调数据跨命名空间一致性 |
| **令牌认证** | 所有请求需携带 `X-Token` 头，防止未授权访问 |
| **详细日志** | 参数、返回值、NaN 统计等诊断信息完整记录 |
| **端口复用** | 自动清理端口占用，支持策略重启无需重启 QMT |
| **自检机制** | 服务启动 1 秒后自动请求自身，验证服务可用性 |
| **GBK 兼容** | `ensure_ascii=True` 避免 GBK 环境下编码问题 |

---

## 安装与配置

### 前提条件

- 已安装 QMT 大智慧极速策略交易系统
- QMT 内置 Python 3.6+（含 Tornado 库）
- 外部 Python 环境安装 `requests` 库

### 服务端部署

1. **打开 QMT 策略编辑器**，创建新策略
2. **将 `qmt_server.py` 的全部内容粘贴**到策略编辑器中
3. **修改配置项**（文件顶部）：

```python
#encoding:gbk    ← 此行不可修改！

ACCOUNT_ID = '你的QMT账号'    # 填入实际账号
TOKEN = "123456789"           # 令牌，客户端需一致
PORT = 8888                   # 服务端口
```

4. **保存并运行策略**，日志中应出现：

```
QMT HTTP Server 启动于 http://127.0.0.1:8888 (账号ID: xxxxx)
QMT HTTP Server 已监听 http://127.0.0.1:8888
QMT HTTP Server 自检通过！服务已就绪 http://127.0.0.1:8888
```

5. **确认服务可用**：在外部 Python 中执行：

```python
from qmt_client import QMTClient
client = QMTClient()
print(client.python_version())
```

### 客户端配置

```python
from qmt_client import QMTClient

# 默认连接本机 8888 端口
client = QMTClient()

# 自定义地址和令牌
client = QMTClient(base_url="http://127.0.0.1:8888")
# 令牌在 qmt_client.py 顶部的 TOKEN 变量中修改
```

---

## API 参考

### 1. 系统接口

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| `python_version()` | GET | `/api/sys/python_version` | 获取 QMT 内置 Python 版本 |
| `close()` | POST | `/api/sys/shutdown` | 关闭 HTTP 服务（谨慎使用） |

### 2. 上下文属性查询

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| `get_context_period()` | GET | `/api/context/period` | 当前周期 |
| `get_context_barpos()` | GET | `/api/context/barpos` | 当前 K 线索引号 |
| `get_context_time_tick_size()` | GET | `/api/context/time_tick_size` | 当前 K 线数目 |
| `get_context_stockcode()` | GET | `/api/context/stockcode` | 当前主图品种代码 |
| `get_context_dividend_type()` | GET | `/api/context/dividend_type` | 当前复权方式 |
| `get_context_market()` | GET | `/api/context/market` | 当前主图市场 |
| `get_context_do_back_test()` | GET | `/api/context/do_back_test` | 是否回测模式 |
| `get_context_benchmark()` | GET | `/api/context/benchmark` | 回测基准 |
| `get_context_capital()` | GET | `/api/context/capital` | 回测初始资金 |
| `get_context_universe()` | GET | `/api/context/universe` | 股票池 |
| `get_context_start()` | GET | `/api/context/start` | 回测开始时间 |
| `get_context_end()` | GET | `/api/context/end` | 回测结束时间 |

### 3. 上下文设置

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| `set_universe(stock_list)` | POST | `/api/context/set_universe` | 设置股票池 |
| `set_account(accountid)` | POST | `/api/context/set_account` | 设置账户 |
| `set_output_index_property(...)` | POST | `/api/context/set_output_index_property` | 设置输出指标属性 |
| `set_commission(comtype, com)` | POST | `/api/context/set_commission` | 设置手续费 |
| `set_slippage(b_flag, slippage)` | POST | `/api/context/set_slippage` | 设置滑点 |

### 4. 数据查询

#### 行情数据

| 接口 | 路径 | 说明 |
|------|------|------|
| `get_full_tick(stocks)` | `/api/data/full_tick` | 获取最新全推行情 |
| `get_market_data(...)` | `/api/data/market_data` | 获取行情数据（DataFrame） |
| `get_market_data_ex(stock_code, fields, period, ...)` | `/api/data/market_data_ex` | 获取扩展行情（Level2） |
| `get_local_data(stock_code, start_time, ...)` | `/api/data/local_data` | 获取本地已下载数据 |
| `get_history_data(length, period, field, ...)` | `/api/data/history_data` | 获取历史行情（依赖 handlebar） |
| `download_history_data(stockcode, period, ...)` | `/api/data/download_history_data` | 下载历史数据到本地 |

#### 基础数据

| 接口 | 路径 | 说明 |
|------|------|------|
| `get_stock_name(stockcode)` | `/api/data/stock_name` | 获取股票名称 |
| `get_open_date(stockcode)` | `/api/data/open_date` | 获取上市日期 |
| `get_last_volume(stockcode)` | `/api/data/last_volume` | 获取最新流通股本 |
| `get_instrumentdetail(stockcode)` | `/api/data/instrumentdetail` | 获取合约详情 |
| `get_total_share(stockcode)` | `/api/data/total_share` | 获取总股本 |
| `get_trading_dates(stockcode, ...)` | `/api/data/trading_dates` | 获取交易日列表 |
| `get_close_price(stockcode, period, timetag)` | `/api/data/close_price` | 按时间戳获取收盘价 |
| `get_close_price_by_date(stockcode, period, strdate)` | `/api/data/close_price_by_date` | 按日期获取收盘价 |
| `get_turnover_rate(stock_list, ...)` | `/api/data/turnover_rate` | 获取换手率 |
| `get_svol(stockcode)` | `/api/data/svol` | 获取卖量 |
| `get_bvol(stockcode)` | `/api/data/bvol` | 获取买量 |
| `get_bar_timetag(index)` | `/api/data/bar_timetag` | 获取 K 线时间戳 |
| `get_tick_timetag()` | `/api/data/tick_timetag` | 获取分笔时间戳 |
| `timetag_to_datetime(timetag, fmt)` | `/api/data/timetag_to_datetime` | 时间戳转日期字符串 |
| `get_date_location(strdate)` | `/api/data/date_location` | 日期对应 K 线索引 |
| `get_divid_factors(stockcode)` | `/api/data/divid_factors` | 获取除权因子 |
| `get_market_time()` | `/api/data/market_time` | 获取交易时间段 |

#### 板块与行业

| 接口 | 路径 | 说明 |
|------|------|------|
| `get_sector(sector)` | `/api/data/sector` | 获取指数成分股 |
| `get_industry(industry)` | `/api/data/industry` | 获取行业成分股 |
| `get_stock_list_in_sector(sectorname)` | `/api/data/stock_list_in_sector` | 获取板块成分股 |
| `get_weight_in_index(indexcode, stockcode)` | `/api/data/weight_in_index` | 获取指数权重 |

#### 财务数据

| 接口 | 路径 | 说明 |
|------|------|------|
| `get_financial_data(fieldList, stockList, ...)` | `/api/data/financial_data` | 获取财务数据 |
| `get_raw_financial_data(field_list, stock_list, ...)` | `/api/data/raw_financial_data` | 获取原始财务数据 |
| `get_factor_data(fields, stock_code_or_list, ...)` | `/api/data/factor_data` | 获取因子数据 |
| `get_longhubang(stock_list, ...)` | `/api/data/longhubang` | 获取龙虎榜数据 |
| `get_top10_share_holder(stock_list, ...)` | `/api/data/top10_share_holder` | 获取十大股东 |
| `get_his_st_data(stockCode)` | `/api/data/his_st_data` | 获取历史 ST 数据 |
| `get_his_index_data(index)` | `/api/data/his_index_data` | 获取历史指标数据 |
| `get_st_status(stock_code)` | `/api/data/st_status` | 获取 ST 状态 |
| `get_risk_free_rate(index)` | `/api/data/risk_free_rate` | 获取无风险利率 |
| `get_net_value(barpositon)` | `/api/data/net_value` | 获取净值 |
| `get_commission()` | `/api/data/commission` | 获取手续费设置 |
| `get_slippage()` | `/api/data/slippage` | 获取滑点设置 |

#### 衍生品数据

| 接口 | 路径 | 说明 |
|------|------|------|
| `get_main_contract(codemarket)` | `/api/data/main_contract` | 获取主力合约 |
| `get_contract_multiplier(contractcode)` | `/api/data/contract_multiplier` | 获取合约乘数 |
| `get_contract_expire_date(codemarket)` | `/api/data/contract_expire_date` | 获取合约到期日 |
| `get_option_detail(optioncode)` | `/api/data/option_detail` | 获取期权详情 |
| `get_option_detail_data(stockcode)` | `/api/data/option_detail_data` | 获取期权详细数据 |
| `get_option_list(undl_code, ...)` | `/api/data/option_list` | 获取期权列表 |
| `get_option_undl_data(undl_code_ref)` | `/api/data/option_undl_data` | 获取期权标的物数据 |
| `get_his_contract_list(market)` | `/api/data/his_contract_list` | 获取历史合约列表 |
| `get_option_iv(optioncode)` | `/api/data/option_iv` | 获取期权隐含波动率 |
| `bsm_price(optionType, ...)` | `/api/data/bsm_price` | B-S-M 定价 |
| `bsm_iv(optionType, ...)` | `/api/data/bsm_iv` | B-S-M 隐含波动率 |
| `get_option_subject_position(account, ...)` | `/api/data/option_subject_position` | 获取期权标的持仓 |
| `get_comb_option(account)` | `/api/data/comb_option` | 获取组合期权 |

#### 跨境数据

| 接口 | 路径 | 说明 |
|------|------|------|
| `get_north_finance_change(period)` | `/api/data/north_finance_change` | 获取北向资金变化 |
| `get_hkt_exchange_rate()` | `/api/data/hkt_exchange_rate` | 获取港股通汇率 |
| `get_hkt_details(stock_code)` | `/api/data/hkt_details` | 获取港股通明细 |
| `get_hkt_statistics(stock_code)` | `/api/data/hkt_statistics` | 获取港股通统计 |

#### ETF 数据

| 接口 | 路径 | 说明 |
|------|------|------|
| `get_etf_info(stockcode)` | `/api/data/etf_info` | 获取 ETF 信息 |
| `get_etf_iopv(stockcode)` | `/api/data/etf_iopv` | 获取 ETF IOPV（参考净值） |

#### 其他数据

| 接口 | 路径 | 说明 |
|------|------|------|
| `get_all_subscription()` | `/api/data/all_subscription` | 获取所有订阅信息 |
| `load_stk_list(dirfile, namefile)` | `/api/data/load_stk_list` | 加载股票列表文件 |
| `load_stk_vol_list(dirfile, namefile)` | `/api/data/load_stk_vol_list` | 加载股票量列表文件 |
| `get_basket(basket_name)` | `/api/data/get_basket` | 获取篮子 |
| `set_basket(basket_name, stock_list)` | `/api/data/set_basket` | 设置篮子 |

### 5. 订阅接口

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| `subscribe_quote(stock_code, period, dividend_type)` | POST | `/api/data/subscribe_quote` | 订阅行情 |
| `subscribe_whole_quote(code_list)` | POST | `/api/data/subscribe_whole_quote` | 订阅全推行情 |
| `get_sub_tick_cache()` | GET | `/api/data/sub_tick_cache` | 获取全推行情缓存 |
| `get_sub_quote_cache()` | GET | `/api/data/sub_quote_cache` | 获取订阅行情缓存 |
| `unsubscribe_quote(sub_id)` | POST | `/api/data/unsubscribe_quote` | 取消订阅 |

> 订阅数据由 QMT 回调自动写入缓存，客户端通过 `get_sub_tick_cache()` / `get_sub_quote_cache()` 轮询获取。

### 6. 判定函数

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| `is_last_bar()` | GET | `/api/check/is_last_bar` | 是否最后一根 K 线 |
| `is_new_bar()` | GET | `/api/check/is_new_bar` | 是否新 K 线 |
| `is_suspended_stock(stockcode)` | POST | `/api/check/is_suspended_stock` | 是否停牌 |
| `is_sector_stock(sectorname, market, stockcode)` | POST | `/api/check/is_sector_stock` | 是否板块成分股 |
| `is_typed_stock(stocktypenum, market, stockcode)` | POST | `/api/check/is_typed_stock` | 是否某类型股票 |
| `get_industry_name_of_stock(industryType, stockcode)` | POST | `/api/check/get_industry_name_of_stock` | 获取股票行业名称 |

### 7. 交易接口

#### 股票交易

| 接口 | 路径 | 说明 |
|------|------|------|
| `buy_stock(stock, price, volume, pr_type)` | `/api/order/buy` | 买入股票 |
| `sell_stock(stock, price, volume, pr_type)` | `/api/order/sell` | 卖出股票 |
| `passorder(opType, orderType, stock, prType, price, volume, quickTrade)` | `/api/trade/passorder` | 通用下单 |
| `algo_passorder(opType, ...)` | `/api/trade/algo_passorder` | 算法下单 |
| `smart_algo_passorder(opType, ...)` | `/api/trade/smart_algo_passorder` | 智能算法下单 |

#### 便捷下单

| 接口 | 路径 | 说明 |
|------|------|------|
| `order_lots(stock, lots, style, price, accId)` | `/api/trade/order_lots` | 按手数下单 |
| `order_value(stock, value, style, price, accId)` | `/api/trade/order_value` | 按金额下单 |
| `order_percent(stock, percent, style, price, accId)` | `/api/trade/order_percent` | 按比例下单 |
| `order_target_value(stock, tar_value, ...)` | `/api/trade/order_target_value` | 目标金额下单 |
| `order_target_percent(stock, tar_percent, ...)` | `/api/trade/order_target_percent` | 目标比例下单 |
| `order_shares(stock, shares, style, price, accId)` | `/api/trade/order_shares` | 按股数下单 |
| `do_order()` | `/api/trade/do_order` | 执行下单 |

#### 期货交易

| 接口 | 路径 | 说明 |
|------|------|------|
| `buy_open(stock, amount, ...)` | `/api/trade/futures/buy_open` | 买入开仓 |
| `buy_close_tdayfirst(stock, amount, ...)` | `/api/trade/futures/buy_close_tdayfirst` | 买入平仓（今仓优先） |
| `buy_close_ydayfirst(stock, amount, ...)` | `/api/trade/futures/buy_close_ydayfirst` | 买入平仓（昨仓优先） |
| `sell_open(stock, amount, ...)` | `/api/trade/futures/sell_open` | 卖出开仓 |
| `sell_close_tdayfirst(stock, amount, ...)` | `/api/trade/futures/sell_close_tdayfirst` | 卖出平仓（今仓优先） |
| `sell_close_ydayfirst(stock, amount, ...)` | `/api/trade/futures/sell_close_ydayfirst` | 卖出平仓（昨仓优先） |

#### 止损止盈

| 接口 | 路径 | 说明 |
|------|------|------|
| `stoploss_limitprice(...)` | `/api/trade/stoploss_limitprice` | 限价止损 |
| `stoploss_marketprice(...)` | `/api/trade/stoploss_marketprice` | 市价止损 |

#### 期权组合

| 接口 | 路径 | 说明 |
|------|------|------|
| `make_option_combination(account, opt_comb_list, ...)` | `/api/trade/make_option_combination` | 组合期权 |
| `release_option_combination(account, opt_comb_list, ...)` | `/api/trade/release_option_combination` | 解除期权组合 |

#### 撤单

| 接口 | 路径 | 说明 |
|------|------|------|
| `cancel_order(stock, volume, account)` | `/api/order/cancel_order` | 按股票和数量撤单 |
| `cancel_all_orders(account)` | `/api/order/cancel_all` | 一键撤所有活跃订单 |
| `cancel_order_by_id(orderId, accountType)` | `/api/trade/cancel` | 按 ID 撤单 |

#### 任务管理

| 接口 | 路径 | 说明 |
|------|------|------|
| `cancel_task(taskId, accountType)` | `/api/trade/cancel_task` | 取消任务 |
| `pause_task(taskId, accountType)` | `/api/trade/pause_task` | 暂停任务 |
| `resume_task(taskId, accountType)` | `/api/trade/resume_task` | 恢复任务 |

### 8. 账户与订单查询

| 接口 | 路径 | 说明 |
|------|------|------|
| `get_holding(account)` | `/api/holding` | 查询持仓 |
| `get_total_money(account)` | `/api/money/total` | 查询总资产 |
| `get_available_money(account)` | `/api/money/available` | 查询可用资金 |
| `get_order_status(account)` | `/api/order/status` | 查询委托状态 |
| `get_deal(account)` | `/api/order/deal` | 查询成交 |
| `get_trade_detail_data(account, datatype)` | `/api/trade/trade_detail_data` | 交易明细数据 |
| `get_value_by_order_id(orderId, ...)` | `/api/trade/value_by_order_id` | 按委托号查询 |
| `get_last_order_id(account, datatype)` | `/api/trade/last_order_id` | 获取最近委托号 |
| `can_cancel_order(orderId, accountType)` | `/api/trade/can_cancel_order` | 判断是否可撤单 |
| `get_debt_contract(accId)` | `/api/trade/debt_contract` | 查询负债合约 |
| `get_assure_contract(accId)` | `/api/trade/assure_contract` | 查询担保合约 |
| `get_enable_short_contract(accId)` | `/api/trade/enable_short_contract` | 查询可融券合约 |
| `get_ipo_data(typ)` | `/api/trade/ipo_data` | 获取新股新债信息 |
| `get_new_purchase_limit(accid)` | `/api/trade/new_purchase_limit` | 获取申购额度 |
| `get_smart_algo_param(algoList)` | `/api/trade/smart_algo_param` | 获取智能算法参数 |
| `query_credit_account(accid, seq)` | `/api/trade/query_credit_account` | 查询两融账户 |
| `query_credit_opvolume(accid, ...)` | `/api/trade/query_credit_opvolume` | 查询两融可下单量 |
| `get_unclosed_compacts(account, ...)` | `/api/trade/unclosed_compacts` | 获取未平仓合约 |
| `get_closed_compacts(account, ...)` | `/api/trade/closed_compacts` | 获取已平仓合约 |

### 9. 扩展数据与引用函数

| 接口 | 路径 | 说明 |
|------|------|------|
| `ext_data(extdataname, stockcode, deviation)` | `/api/ext/ext_data` | 获取扩展数据 |
| `ext_data_rank(extdataname, stockcode, deviation)` | `/api/ext/ext_data_rank` | 获取扩展数据排名 |
| `ext_data_rank_range(extdataname, stockcode, begintime, endtime)` | `/api/ext/ext_data_rank_range` | 获取排名范围 |
| `ext_data_range(extdataname, stockcode, begintime, endtime)` | `/api/ext/ext_data_range` | 获取数据值范围 |
| `ext_data_range(extdataname, stockcode, begintime, endtime)` | `/api/ext/ext_all_data` | 获取全部扩展数据 |
| `get_factor_value(factorname, stockcode, deviation)` | `/api/ext/get_factor_value` | 获取因子数值（依赖 handlebar） |
| `get_factor_rank(factorname, stockcode, deviation)` | `/api/ext/get_factor_rank` | 获取因子排名 |
| `call_formula(formula_name, params)` | `/api/ext/call_formula` | 调用公式 |

### 10. 板块管理

| 接口 | 路径 | 说明 |
|------|------|------|
| `create_sector(parent_node, sector_name, overwrite)` | `/api/sector/create` | 创建板块 |
| `create_sector_folder(parent_node, folder_name, overwrite)` | `/api/sector/create_folder` | 创建板块文件夹 |
| `get_sector_list(node)` | `/api/sector/list` | 获取板块目录 |
| `reset_sector_stock_list(sector, stock_list)` | `/api/sector/reset_stocks` | 重置板块成分股 |
| `add_stock_to_sector(sector, stock_code)` | `/api/sector/add_stock` | 添加股票到板块 |
| `remove_stock_from_sector(sector, stock_code)` | `/api/sector/remove_stock` | 从板块移除股票 |

### 11. 兼容路由

为向后兼容保留的简化路由：

| 接口 | 路径 | 说明 |
|------|------|------|
| `get_holding(account)` | `/api/holding` | 持仓查询 |
| `get_total_money(account)` | `/api/money/total` | 总资产查询 |
| `get_available_money(account)` | `/api/money/available` | 可用资金查询 |
| `buy_stock(...)` | `/api/order/buy` | 买入 |
| `sell_stock(...)` | `/api/order/sell` | 卖出 |
| `get_order_status(account)` | `/api/order/status` | 委托状态 |
| `cancel_all_orders(account)` | `/api/order/cancel_all` | 一键撤单 |
| `cancel_order(stock, volume, account)` | `/api/order/cancel_order` | 按规则撤单 |
| `get_deal(account)` | `/api/order/deal` | 成交查询 |

---

## 客户端使用

### 基本用法

```python
from qmt_client import QMTClient

# 创建客户端
client = QMTClient()  # 默认 http://127.0.0.1:8888

# 查询 Python 版本
print(client.python_version())
# {"python_version": "3.6.8 ...", "python_version_info": {"major": 3, "minor": 6, ...}}

# 查询持仓（返回以股票代码为key的字典）
holding = client.get_holding("stock")
# {"600988.SH": {"StockCode": "600988.SH", "StockName": "赤峰黄金", "Volume": 3000, ...}}

# 查询资金
print("总资产:", client.get_total_money("stock"))
# {"total_money": 9988177.97}
print("可用资金:", client.get_available_money("stock"))
# {"available_money": 9130915.27}
```

### 行情数据

```python
# 获取最新行情（返回以股票代码为key的字典，无 'data' 包装层）
tick = client.get_full_tick("600000.SH")
# {"600000.SH": {"lastPrice": 8.52, "lastClose": 8.50, "bidPrice": [8.51, ...], "askPrice": [8.52, ...], ...}}

# 多只股票
tick = client.get_full_tick("600000.SH,000001.SZ")
# {"600000.SH": {...}, "000001.SZ": {...}}

# 获取 K 线数据
kline = client.get_market_data_ex(
    stock_code=["600000.SH", "000001.SZ"],
    fields="open,high,low,close,volume",
    period="1d",
    start_time="20250101",
    end_time="20250630"
)
# {"data": {"600000.SH": {"times": [...], "open": [...], ...}, ...}}

# 获取股票名称
name = client.get_stock_name("600000.SH")
# {"stockcode": "600000.SH", "name": "浦发银行"}

# 获取板块成分股
stocks = client.get_sector("000300.SH")
# {"sector": "000300.SH", "stocks": ["600000.SH", ...]}
```

### 交易下单

```python
# 买入（指定价）
result = client.buy_stock("600000.SH", 8.50, 100, pr_type=11)
# {"status": "success", "order_ref": "123456", "action": "buy", "stock": "600000.SH", "message": "下单成功"}

# 卖出
result = client.sell_stock("600000.SH", 8.60, 100, pr_type=11)

# 通用下单 (passorder)
result = client.passorder(
    opType=0,        # 0=买入 1=卖出
    orderType=1101,  # 股票
    stock="600000.SH",
    prType=11,       # 指定价
    price=8.50,
    volume=100,
    quickTrade=2     # 2=允许快速交易
)

# 查询委托（返回 {"orders": [...]}）
orders = client.get_order_status("stock")
# {"orders": [{"m_strInstrumentID": "600000", "m_nDirection": 48, "m_dLimitPrice": 8.50, "m_strOrderSysID": "8384", ...}]}

# 查询成交（返回 {"deals": [...]}）
deals = client.get_deal("stock")
# {"deals": [{"m_strInstrumentID": "600000", "m_dPrice": 8.50, "m_nVolume": 100, "m_strTradeTime": "093005", ...}]}

# 查询持仓（返回 {股票代码: 持仓信息}）
holding = client.get_holding("stock")
# {"600000.SH": {"StockCode": "600000.SH", "Volume": 100, "CanUseVolume": 100, "OpenPrice": 8.50, ...}}

# 按 ID 撤单
client.cancel_order_by_id("123456")

# 一键撤所有
client.cancel_all_orders("stock")
```

> **注意**：委托/成交记录中的 `m_strInstrumentID` **不含交易所后缀**（如 `"600000"` 而非 `"600000.SH"`），需要根据代码前缀自行补全。持仓返回的 `StockCode` 则带后缀。

### 下单选价类型（prType）

| 值 | 说明 |
|----|------|
| 0-4 | 卖5价~卖1价 |
| 5 | 最新价 |
| 6-10 | 买1价~买5价 |
| 11 | 指定价（模型价） |
| 12 | 涨跌停价 |
| 13 | 挂单价 |
| 14 | 对手价 |
| 42-48 | 各交易所特殊委托方式 |
| 49 | 盘后定价 |

### 委托状态码

| 值 | 说明 |
|----|------|
| 48 | 未报 |
| 49 | 待报 |
| 50 | 已报 |
| 51 | 已报待撤 |
| 52 | 部成待撤 |
| 53 | 部撤 |
| 54 | 已撤 |
| 55 | 部成 |
| 56 | 已成 |
| 57 | 废单 |

### 订阅行情

```python
# 订阅全推行情
client.subscribe_whole_quote(["600000.SH", "000001.SZ"])

# 轮询获取推送缓存
import time
while True:
    data = client.get_sub_tick_cache()
    print(data)
    time.sleep(1)

# 取消订阅
client.unsubscribe_quote(sub_id)
```

---

## 测试套件

项目包含完整的测试套件，位于 `test/` 目录。

### 测试文件说明

| 文件 | 编号 | 测试内容 |
|------|------|----------|
| `test_01_system.py` | 01 | 系统信息 + 兼容路由 |
| `test_02_context.py` | 02 | ContextInfo 属性与设置 |
| `test_03_quote.py` | 03 | 实时行情数据 |
| `test_04_history.py` | 04 | 历史数据 + 交易日期 |
| `test_05_finance.py` | 05 | 财务/基本面数据 |
| `test_06_derivative.py` | 06 | 衍生品数据（期货/期权） |
| `test_07_cross_border.py` | 07 | 跨境资金数据 |
| `test_08_judge.py` | 08 | 判定函数 |
| `test_09_account.py` | 09 | 账户与订单查询 |
| `test_10_subscribe.py` | 10 | 行情订阅 |
| `test_11_ext.py` | 11 | 扩展数据与引用函数 |
| `test_20_trade.py` | 20 | 全部交易操作 |

### 运行测试

```bash
# 运行所有数据测试（01-11）
python test/run_all_tests.py

# 运行全部测试（含交易）
python test/run_all_tests.py --all

# 只运行交易测试
python test/run_all_tests.py --trade

# 运行指定编号
python test/run_all_tests.py 3 5

# 交易测试自动确认（跳过手动确认）
python test/run_all_tests.py --yes

# 单独运行某个测试
python test/test_01_system.py
```

### assert_test 框架

`test_base.py` 提供了统一的测试基础设施：

```python
from test_base import setup_logging, assert_test, print_summary, QMTClient

setup_logging("test_my_feature")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": [], "warn": []}

# 无断言测试
assert_test(results, "接口名称", lambda: client.some_api())

# 带断言测试
assert_test(results, "获取行情", lambda: client.get_full_tick("600000.SH"), [
    (("600000.SH", "lastPrice"), lambda v: v is not None and v > 0, "最新价>0"),
    (("600000.SH", "volume"), lambda v: v is not None and v > 0, "成交量>0"),
])

# 危险操作（需手动确认）
assert_test(results, "买入", lambda: client.buy_stock("600000.SH", 8.50, 100),
    dangerous=True, confirm_func=lambda msg: input(msg + " (y/N): ") == 'y')

# 打印汇总
ok = print_summary(results)
```

**断言格式**：`((路径元组), 检查函数, 描述)`

- 路径元组用于从返回的 dict 中逐层取值（类似 `data["600000.SH"]["lastPrice"]`）
- 检查函数接收取到的值，返回 `True` / `False`

### 日志

测试日志输出到 `test/log/` 目录，文件名格式为 `{prefix}_{YYYYMMDD_HHMMSS}.log`，同时输出到控制台。

---

## 注意事项

### 编码声明

```python
#encoding:gbk
```

**此行不可修改！** QMT 策略编辑器强制要求 GBK 编码声明，删除或修改会导致运行失败。

### Python 3.6 兼容性

QMT 内置 Python 为 3.6 版本，**不支持 f-string**。`qmt_server.py` 中所有字符串格式化均使用 `.format()` 方式：

```python
# 正确
"端口 {} 被占用".format(port)

# 错误（Python 3.6 不支持）
f"端口 {port} 被占用"
```

### QMT 白名单限制

QMT 的 Python 环境有模块白名单限制，**不能使用 `subprocess` 和 `socket` 包**：

```python
# 不可用
import subprocess  # 白名单限制
import socket      # 白名单限制

# 替代方案
os.system('taskkill /F /PID {}'.format(pid))  # 用 os.system 替代 subprocess
HTTPServer(app).listen(PORT)                    # Tornado 自带 listen，无需 socket
```

### handlebar 上下文依赖

以下 API 依赖 `handlebar` 回调上下文，在 HTTP Handler 中直接调用可能返回空数据：

- `get_history_data()` — 需先 `set_universe()`，或使用 `get_local_data()` / `get_market_data_ex()` 替代
- `get_factor_value()` — 全局函数，依赖 handlebar 上下文，可能无法在 HTTP 请求中获取
- `order_lots()` / `order_value()` / `order_percent()` 等便捷下单函数 — 依赖 handlebar 上下文中的账户信息

### passorder 异步特性

`passorder` 是**异步下单**，调用后不会立即返回订单号。服务端通过以下机制处理：

1. 下单前记录当前活跃委托 ID 集合（`_collect_order_ids()`）
2. 下单后轮询查询新出现的委托（`_find_new_order_ref()`，最多等待 2 秒）
3. 返回匹配的新委托 ID 作为 `order_ref`

```python
result = client.passorder(0, 1101, "600000.SH", 11, 8.50, 100)
# {"status": "success", "order_ref": "123456"}
```

如需确认订单状态，请通过 `get_order_status()` 或 `get_trade_detail_data()` 查询。

### 日志目录

- 服务端日志：由 QMT 策略编辑器管理
- 测试日志：`test/log/` 目录，文件名含时间戳避免覆盖
- 临时文件：`_port_check.tmp`（端口检查临时文件，自动清理）

### 交易测试安全

- 交易测试（`test_20_trade.py`）默认需手动确认每步操作
- 使用 `--yes` 参数可自动确认（**慎用！会产生真实交易**）
- 测试标的为 513090.SH（T+0 ETF），买入价 = 现价 + 0.015，卖出价 = 现价 - 0.015

---

## 项目结构

```
qmt_bridge/
├── qmt_server.py          # 服务端 - 在 QMT 策略中运行，Tornado HTTP Server
├── qmt_client.py          # 客户端 - 外部 Python 调用，基于 requests
├── README.md              # 本文档
├── .gitignore
├── log/                   # 测试日志目录（自动创建）
├── doc/
│   └── 迅投QMT极速策略交易系统_模型资料_Python_API_说明文档_Python3.pdf
└── test/
    ├── test_base.py           # 测试基础设施（日志、断言框架、工具函数）
    ├── test_01_system.py      # 系统信息测试
    ├── test_02_context.py     # ContextInfo 属性测试
    ├── test_03_quote.py       # 实时行情测试
    ├── test_04_history.py     # 历史数据测试
    ├── test_05_finance.py     # 财务数据测试
    ├── test_06_derivative.py  # 衍生品数据测试
    ├── test_07_cross_border.py# 跨境数据测试
    ├── test_08_judge.py       # 判定函数测试
    ├── test_09_account.py     # 账户查询测试
    ├── test_10_subscribe.py   # 行情订阅测试
    ├── test_11_ext.py         # 扩展数据测试
    ├── test_20_trade.py       # 交易操作测试
    └── run_all_tests.py       # 一键运行全部测试
```

---

## 故障排除

### 连接失败

**症状**：`ConnectionRefusedError` 或 `requests.ConnectionError`

**排查**：
1. 确认 QMT 策略已运行并显示 "自检通过" 日志
2. 检查端口是否被其他程序占用：`netstat -ano | findstr :8888`
3. 确认防火墙未阻止 127.0.0.1:8888
4. 尝试重启 QMT 策略

### 认证失败

**症状**：HTTP 401 错误

**排查**：
1. 确认客户端 `TOKEN` 与服务端一致
2. 检查请求头是否包含 `X-Token`
3. 确认 Token 值无前后空格

### 数据返回空值

**症状**：API 返回 `None`、`{}` 或空列表

**排查**：
1. **先下载历史数据**：部分数据需要先 `download_history_data()` 才能查询
2. 检查股票代码格式：需带后缀（如 `600000.SH`、`000001.SZ`）
3. 检查日期范围是否合理
4. `get_history_data` 依赖 handlebar 上下文，建议使用 `get_local_data` 或 `get_market_data_ex` 替代

### JSON 序列化失败

**症状**：`ValueError: Out of range float values are not JSON compliant`

**排查**：
1. 已通过 `safe_json_dumps()` 自动处理，NaN/Inf 会转为 `null`
2. 如果仍出现，检查是否有特殊的 QMT 返回对象未被 `_extract_attrs()` 覆盖
3. 查看服务端日志中的 NaN 转换统计

### 中文乱码

**症状**：返回的中文显示为 `\uXXXX` 转义序列

**说明**：
- 服务端使用 `ensure_ascii=True` 避免 GBK 环境下的编码问题
- 客户端通过 `resp.encoding = 'utf-8'` 正确解码
- 这是正常行为，JSON 解析后中文会正确显示

### 端口占用

**症状**：策略重启时报端口占用错误

**排查**：
1. 服务端已内置 `_kill_port_occupier()` 自动清理机制
2. 如果自动清理失败，手动执行：`taskkill /F /PID <占用进程PID>`
3. 等待 1-2 秒后重新运行策略

### get_trading_dates 返回空

**症状**：`get_trading_dates` 返回空列表

**排查**：
1. 需先下载对应指数数据（如 `download_history_data("000300.SH")`）
2. 服务端已实现降级方案：从 `get_local_data` 的毫秒时间戳 key 中提取交易日
3. 检查日期参数格式是否为 `YYYYMMDD`

### 订阅数据不更新

**症状**：`get_sub_tick_cache()` 返回空

**排查**：
1. 确认策略周期设置为 tick 级别（QMT 策略周期影响订阅更新频率）
2. 使用 `get_full_tick()` 主动获取初始数据
3. 检查订阅回调日志是否被触发
4. 确认股票代码格式正确

### 下单后无委托

**症状**：`passorder` 返回成功但查不到委托

**排查**：
1. 确认在交易时段（9:15-15:00）
2. 检查价格是否合理（买入价 ≥ 卖一价，卖出价 ≤ 买一价）
3. `passorder` 是异步的，等待 1-2 秒后再查询
4. 检查账户是否有足够资金/持仓
5. 查看服务端日志中的 `_find_new_order_ref` 诊断信息

### API 返回格式说明

**各 API 的返回格式并不统一**，没有通用的 `{"data": ...}` 包装层。常见格式：

| 类型 | 示例 | 适用 API |
|------|------|----------|
| 带语义 key | `{"stockcode": "...", "name": "..."}` | 大部分单值查询（get_stock_name, get_open_date 等） |
| 股票代码为 key | `{"600000.SH": {lastPrice: 8.52, ...}}` | get_full_tick, get_holding |
| 列表包装 | `{"orders": [...]}`, `{"deals": [...]}` | get_order_status, get_deal |
| data 包装 | `{"data": {...}}` | get_market_data_ex, get_market_data, get_local_data |
| 简单值 | `{"total_money": 9988177.97}` | get_total_money, get_available_money |

具体格式请参考 `qmt_client.py` 中各方法的 docstring。
