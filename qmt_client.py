# -*- coding: utf-8 -*-
# author公众号：可转债量化分析
import requests
import json

TOKEN = "123456789"


class QMTClient:
    def __init__(self, base_url="http://127.0.0.1:8888"):
        self.base = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json; charset=utf-8"})
        self.session.headers.update({"X-Token": TOKEN})

    def _req(self, method, path, **kwargs):
        url = f"{self.base}{path}"
        try:
            resp = self.session.request(method, url, timeout=10, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"error": str(e), "status_code": getattr(e.response, 'status_code', 500)}

    def get_holding(self, account='stock'):
        return self._req('GET', f'/api/holding?account={account}')

    def get_total_money(self, account='stock'):
        return self._req('POST', f'/api/money/total', json={"account": account})

    def get_available_money(self, account='stock'):
        return self._req('POST', f'/api/money/available', json={"account": account})

    def buy_stock(self, stock, price, volume, pr_type=11):
        """
        prType(下单选价类型):（特别的对于套利：这个prType只对篮子起作用,期货的采用默认的方式）
        -1:无效(只对于algo_passorder起作用)
        0:卖5价
        1:卖4价
        2:卖3价
        3:卖2价
        4:卖1价
        5:最新价
        6:买1价
        7:买2价(组合不支持)
        8:买3价(组合不支持)
        9:买4价(组合不支持)
        10:买5价(组合不支持)
        11:（指定价）模型价（只对单股情况支持,对组合交易不支持）
        12:涨跌停价
        13:挂单价
        14:对手价
        18:市价最优价[郑商所][期货]
        19:市价即成剩撤[大商所][期货]
        20:市价全额成交或撤[大商所][期货]
        21:市价最优一档即成剩撤[中金所][期货]
        22:市价最优五档即成剩撤[中金所][期货]
        23:市价最优一档即成剩转[中金所][期货]
        24:市价最优五档即成剩转[中金所][期货]
        26:限价即时全部成交否则撤单[上交所|深交所][期权]
        27:市价即成剩撤[上交所][期权]
        28:市价即全成否则撤[上交所][期权]
        29:市价剩转限价[上交所][期权]
        42:最优五档即时成交剩余撤销申报[上交所][股票]
        43:最优五档即时成交剩转限价申报[上交所][股票]
        44:对手方最优价格委托[上交所[股票]][深交所[股票][期权]]
        45:本方最优价格委托[上交所[股票]][深交所[股票][期权]]
        46:即时成交剩余撤销委托[深交所][股票][期权]
        47:最优五档即时成交剩余撤销委托[深交所][股票][期权]
        48:全额成交或撤销委托[深交所][股票][期权]
        49:盘后定价
        :param stock:
        :param price:
        :param volume:
        :param pr_type:
        :return:
        """
        return self._req('POST', '/api/order/buy', json={
            "stock": stock, "price": price, "volume": volume, "prType": pr_type
        })

    def sell_stock(self, stock, price, volume, pr_type=11):
        return self._req('POST', '/api/order/sell', json={
            "stock": stock, "price": price, "volume": volume, "prType": pr_type
        })

    def get_sector(self, sector):
        return self._req('POST', '/api/data/sector', json={
            "sector": sector,
        })

    def get_industry(self, industry):
        return self._req('POST', '/api/data/industry', json={
            "industry": industry,
        })

    def get_full_tick(self, stocks):
        return self._req('POST', f'/api/data/full_tick', json={
            "stocks": stocks})

    def get_market_data_ex(self, stocks: list[str]):
        return self._req('POST', f'/api/data/market_data_ex', json={
            "stocks": stocks})

    def get_order_status(self, account='stock'):
        """
        EEntrustStatus //委托状态
        ENTRUST_STATUS_WAIT_END: 0 //委托状态已经在 ENTRUST_STATUS_CANCELED 或以上，但是成交数额还不够，等成交回报来
        ENTRUST_STATUS_UNREPORTED: 48 //未报
        ENTRUST_STATUS_WAIT_REPORTING: 49 //待报
        ENTRUST_STATUS_REPORTED: 50 //已报
        ENTRUST_STATUS_REPORTED_CANCEL: 51 //已报待撤
        ENTRUST_STATUS_PARTSUCC_CANCEL: 52 //部成待撤
        ENTRUST_STATUS_PART_CANCEL: 53 //部撤
        ENTRUST_STATUS_CANCELED: 54 //已撤
        ENTRUST_STATUS_PART_SUCC: 55 //部成
        ENTRUST_STATUS_SUCCEEDED: 56 //已成
        ENTRUST_STATUS_JUNK: 57 //废单
        ENTRUST_STATUS_DETERMINED: 86 //已确认
        ENTRUST_STATUS_UNKNOWN: 255 //未知
        :return:
        """
        params = {"account": account}
        query = "&".join([f"{k}={v}"for k, v in params.items()])
        return self._req('GET', f'/api/order/status?{query}')

    def cancel_all_orders(self, account='stock'):
        """
        危险操作：一键撤销所有活跃状态的订单
        """
        return self._req('POST', f'/api/order/cancel_all', json={"account": account})

    def cancel_order(self, stock, volume, account='stock'):
        """
        根据股票代码和未成交数量撤单。
        请注意：如果该股票有多笔未成交数量相同的订单，会被全部撤销！
        """
        return self._req('POST', '/api/order/cancel_order', json={
            "stock": stock,
            "volume": volume,
            "account": account
        })

    def python_version(self):
        """
        获取 Python 版本信息
        """
        return self._req('GET', '/api/sys/python_version')

    def close(self):
        """
        关闭整个 QMT HTTP 服务
        """
        return self._req('POST', '/api/sys/shutdown')

    # ============= ContextInfo 属性 =============
    def get_context_period(self):
        return self._req('GET', '/api/context/period')

    def get_context_barpos(self):
        return self._req('GET', '/api/context/barpos')

    def get_context_time_tick_size(self):
        return self._req('GET', '/api/context/time_tick_size')

    def get_context_stockcode(self):
        return self._req('GET', '/api/context/stockcode')

    def get_context_dividend_type(self):
        return self._req('GET', '/api/context/dividend_type')

    def get_context_market(self):
        return self._req('GET', '/api/context/market')

    def get_context_do_back_test(self):
        return self._req('GET', '/api/context/do_back_test')

    def get_context_benchmark(self):
        return self._req('GET', '/api/context/benchmark')

    def get_context_capital(self):
        return self._req('GET', '/api/context/capital')

    def get_context_universe(self):
        return self._req('GET', '/api/context/universe')

    def get_context_start(self):
        return self._req('GET', '/api/context/start')

    def get_context_end(self):
        return self._req('GET', '/api/context/end')

    # ============= ContextInfo 设置 =============
    def set_universe(self, stock_list):
        return self._req('POST', '/api/context/set_universe', json={
            "stock_list": ','.join(stock_list) if isinstance(stock_list, list) else stock_list
        })

    def set_account(self, accountid):
        return self._req('POST', '/api/context/set_account', json={
            "accountid": accountid
        })

    def set_output_index_property(self, index_name, draw_style=0, color='white',
                                  noaxis=False, nodraw=False, noshow=False):
        return self._req('POST', '/api/context/set_output_index_property', json={
            "index_name": index_name, "draw_style": draw_style, "color": color,
            "noaxis": noaxis, "nodraw": nodraw, "noshow": noshow
        })

    # ============= 数据查询 =============
    def get_stock_name(self, stockcode):
        return self._req('POST', '/api/data/stock_name', json={"stockcode": stockcode})

    def get_open_date(self, stockcode):
        return self._req('POST', '/api/data/open_date', json={"stockcode": stockcode})

    def get_last_volume(self, stockcode):
        return self._req('POST', '/api/data/last_volume', json={"stockcode": stockcode})

    def get_bar_timetag(self, index=-1):
        return self._req('POST', '/api/data/bar_timetag', json={"index": index})

    def get_tick_timetag(self):
        return self._req('GET', '/api/data/tick_timetag')

    def get_stock_list_in_sector(self, sectorname):
        return self._req('POST', '/api/data/stock_list_in_sector', json={"sectorname": sectorname})

    def get_weight_in_index(self, indexcode, stockcode):
        return self._req('POST', '/api/data/weight_in_index', json={
            "indexcode": indexcode, "stockcode": stockcode
        })

    def get_contract_multiplier(self, contractcode):
        return self._req('POST', '/api/data/contract_multiplier', json={"contractcode": contractcode})

    def get_risk_free_rate(self, index=-1):
        return self._req('POST', '/api/data/risk_free_rate', json={"index": index})

    def get_date_location(self, strdate):
        return self._req('POST', '/api/data/date_location', json={"strdate": strdate})

    def get_history_data(self, length=10, period='1d', field='close', dividend_type=0, skip_paused=True):
        return self._req('POST', '/api/data/history_data', json={
            "len": length, "period": period, "field": field,
            "dividend_type": dividend_type, "skip_paused": skip_paused
        })

    def get_market_data(self, fields='', stock_code='', start_time='', end_time='',
                        period='1d', dividend_type='none', count=-1):
        return self._req('POST', '/api/data/market_data', json={
            "fields": fields, "stock_code": stock_code, "start_time": start_time,
            "end_time": end_time, "period": period, "dividend_type": dividend_type, "count": count
        })

    def get_divid_factors(self, stockcode):
        return self._req('POST', '/api/data/divid_factors', json={"stockcode": stockcode})

    def get_main_contract(self, codemarket):
        return self._req('POST', '/api/data/main_contract', json={"codemarket": codemarket})

    def timetag_to_datetime(self, timetag, fmt='%Y-%m-%d %H:%M:%S'):
        return self._req('POST', '/api/data/timetag_to_datetime', json={
            "timetag": timetag, "format": fmt
        })

    def get_total_share(self, stockcode):
        return self._req('POST', '/api/data/total_share', json={"stockcode": stockcode})

    def get_trading_dates(self, stockcode='', start_date='', end_date='', count=-1, period='1d'):
        return self._req('POST', '/api/data/trading_dates', json={
            "stockcode": stockcode, "start_date": start_date, "end_date": end_date,
            "count": count, "period": period
        })

    def get_svol(self, stockcode):
        return self._req('POST', '/api/data/svol', json={"stockcode": stockcode})

    def get_bvol(self, stockcode):
        return self._req('POST', '/api/data/bvol', json={"stockcode": stockcode})

    def get_longhubang(self, stock_list, startTime='', endTime=''):
        return self._req('POST', '/api/data/longhubang', json={
            "stock_list": ','.join(stock_list) if isinstance(stock_list, list) else stock_list,
            "startTime": startTime, "endTime": endTime
        })

    def get_top10_share_holder(self, stock_list, data_name='holder', start_time='', end_time=''):
        return self._req('POST', '/api/data/top10_share_holder', json={
            "stock_list": ','.join(stock_list) if isinstance(stock_list, list) else stock_list,
            "data_name": data_name, "start_time": start_time, "end_time": end_time
        })

    def get_option_detail(self, optioncode):
        return self._req('POST', '/api/data/option_detail', json={"optioncode": optioncode})

    def get_turnover_rate(self, stock_list, startTime='', endTime=''):
        return self._req('POST', '/api/data/turnover_rate', json={
            "stock_list": ','.join(stock_list) if isinstance(stock_list, list) else stock_list,
            "startTime": startTime, "endTime": endTime
        })

    def get_etf_info(self, stockcode):
        return self._req('POST', '/api/data/etf_info', json={"stockcode": stockcode})

    def get_etf_iopv(self, stockcode):
        return self._req('POST', '/api/data/etf_iopv', json={"stockcode": stockcode})

    def get_instrumentdetail(self, stockcode):
        return self._req('POST', '/api/data/instrumentdetail', json={"stockcode": stockcode})

    def get_contract_expire_date(self, codemarket):
        return self._req('POST', '/api/data/contract_expire_date', json={"codemarket": codemarket})

    def get_option_undl_data(self, undl_code_ref):
        return self._req('POST', '/api/data/option_undl_data', json={"undl_code_ref": undl_code_ref})

    def get_financial_data(self, fieldList, stockList, startDate='', endDate='', report_type='announce_time'):
        return self._req('POST', '/api/data/financial_data', json={
            "fieldList": ','.join(fieldList) if isinstance(fieldList, list) else fieldList,
            "stockList": ','.join(stockList) if isinstance(stockList, list) else stockList,
            "startDate": startDate, "endDate": endDate, "report_type": report_type
        })

    def get_factor_data(self, fields, stock_code_or_list, start_date='', end_date=''):
        return self._req('POST', '/api/data/factor_data', json={
            "fieldList": ','.join(fields) if isinstance(fields, list) else fields,
            "stockCode": stock_code_or_list if isinstance(stock_code_or_list, str) else '',
            "stockList": ','.join(stock_code_or_list) if isinstance(stock_code_or_list, list) else '',
            "startDate": start_date, "endDate": end_date
        })

    def get_his_st_data(self, stockCode):
        return self._req('POST', '/api/data/his_st_data', json={"stockCode": stockCode})

    def get_his_index_data(self, index):
        return self._req('POST', '/api/data/his_index_data', json={"index": index})

    def get_all_subscription(self):
        return self._req('GET', '/api/data/all_subscription')

    def get_option_list(self, undl_code, dedate='', opttype='', isavailable=True):
        return self._req('POST', '/api/data/option_list', json={
            "undl_code": undl_code, "dedate": dedate, "opttype": opttype, "isavailable": isavailable
        })

    def get_his_contract_list(self, market):
        return self._req('POST', '/api/data/his_contract_list', json={"market": market})

    def get_option_iv(self, optioncode):
        return self._req('POST', '/api/data/option_iv', json={"optioncode": optioncode})

    def bsm_price(self, optionType='C', objectPrices='', strikePrice=0, riskFree=0, sigma=0, days=0, dividend=0):
        return self._req('POST', '/api/data/bsm_price', json={
            "optionType": optionType, "objectPrices": objectPrices,
            "strikePrice": strikePrice, "riskFree": riskFree, "sigma": sigma,
            "days": days, "dividend": dividend
        })

    def bsm_iv(self, optionType='C', objectPrices=0, strikePrice=0, optionPrice=0, riskFree=0, days=0, dividend=0):
        return self._req('POST', '/api/data/bsm_iv', json={
            "optionType": optionType, "objectPrices": objectPrices,
            "strikePrice": strikePrice, "optionPrice": optionPrice,
            "riskFree": riskFree, "days": days, "dividend": dividend
        })

    def get_local_data(self, stock_code, start_time='', end_time='', period='1d', divid_type='none', count=-1):
        return self._req('POST', '/api/data/local_data', json={
            "stock_code": stock_code, "start_time": start_time, "end_time": end_time,
            "period": period, "divid_type": divid_type, "count": count
        })

    def get_close_price(self, stockcode, period='1d', timetag=0):
        return self._req('POST', '/api/data/close_price', json={
            "stockcode": stockcode, "period": period, "timetag": timetag
        })

    def get_close_price_by_date(self, stockcode, period='1d', strdate=''):
        return self._req('POST', '/api/data/close_price_by_date', json={
            "stockcode": stockcode, "period": period, "strdate": strdate
        })

    def download_history_data(self, stockcode, period='1d', start_time='', end_time=''):
        return self._req('POST', '/api/data/download_history_data', json={
            "stockcode": stockcode, "period": period, "start_time": start_time, "end_time": end_time
        })

    # ============= 订阅 =============
    def subscribe_quote(self, stock_code, period='follow', dividend_type='follow'):
        return self._req('POST', '/api/data/subscribe_quote', json={
            "stock_code": stock_code, "period": period, "dividend_type": dividend_type
        })

    def subscribe_whole_quote(self, code_list):
        """订阅全推行情，推送数据会自动缓存，通过 get_sub_tick_cache() 轮询获取"""
        return self._req('POST', '/api/data/subscribe_whole_quote', json={
            "code_list": ','.join(code_list) if isinstance(code_list, list) else code_list
        })

    def get_sub_tick_cache(self):
        """获取 subscribe_whole_quote 订阅缓存的最新推送数据"""
        return self._req('GET', '/api/data/sub_tick_cache')

    def get_sub_quote_cache(self):
        """获取 subscribe_quote 订阅缓存的最新推送数据"""
        return self._req('GET', '/api/data/sub_quote_cache')

    def unsubscribe_quote(self, sub_id):
        return self._req('POST', '/api/data/unsubscribe_quote', json={"sub_id": sub_id})

    # ============= 判定函数 =============
    def is_last_bar(self):
        return self._req('GET', '/api/check/is_last_bar')

    def is_new_bar(self):
        return self._req('GET', '/api/check/is_new_bar')

    def is_suspended_stock(self, stockcode):
        return self._req('POST', '/api/check/is_suspended_stock', json={"stockcode": stockcode})

    def is_sector_stock(self, sectorname, market, stockcode):
        return self._req('POST', '/api/check/is_sector_stock', json={
            "sectorname": sectorname, "market": market, "stockcode": stockcode
        })

    def is_typed_stock(self, stocktypenum, market, stockcode):
        return self._req('POST', '/api/check/is_typed_stock', json={
            "stocktypenum": stocktypenum, "market": market, "stockcode": stockcode
        })

    def get_industry_name_of_stock(self, industryType, stockcode):
        return self._req('POST', '/api/check/get_industry_name_of_stock', json={
            "industryType": industryType, "stockcode": stockcode
        })

    # ============= 交易函数 =============
    def passorder(self, opType, orderType=1101, stock='', prType=11, price=0, volume=0, quickTrade=2):
        return self._req('POST', '/api/trade/passorder', json={
            "opType": opType, "orderType": orderType, "stock": stock,
            "prType": prType, "price": price, "volume": volume, "quickTrade": quickTrade
        })

    def algo_passorder(self, opType, orderType=1101, stock='', prType=-1, price=0, volume=0,
                       strategyName='', quickTrade=2, userOrderId='', userOrderParam=None):
        return self._req('POST', '/api/trade/algo_passorder', json={
            "opType": opType, "orderType": orderType, "stock": stock,
            "prType": prType, "price": price, "volume": volume,
            "strategyName": strategyName, "quickTrade": quickTrade,
            "userOrderId": userOrderId, "userOrderParam": userOrderParam or {}
        })

    def smart_algo_passorder(self, opType, orderType=1101, stock='', prType=-1, price=0, volume=0,
                             smartAlgoType='', limitOverRate=0, minAmountPerOrder=0,
                             startTime='', endTime=''):
        return self._req('POST', '/api/trade/smart_algo_passorder', json={
            "opType": opType, "orderType": orderType, "stock": stock,
            "prType": prType, "price": price, "volume": volume,
            "smartAlgoType": smartAlgoType, "limitOverRate": limitOverRate,
            "minAmountPerOrder": minAmountPerOrder, "startTime": startTime, "endTime": endTime
        })

    def order_lots(self, stock, lots, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/order_lots', json={
            "stock": stock, "lots": lots, "style": style, "price": price, "accId": accId
        })

    def order_value(self, stock, value, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/order_value', json={
            "stock": stock, "value": value, "style": style, "price": price, "accId": accId
        })

    def order_percent(self, stock, percent, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/order_percent', json={
            "stock": stock, "percent": percent, "style": style, "price": price, "accId": accId
        })

    def order_target_value(self, stock, tar_value, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/order_target_value', json={
            "stock": stock, "tar_value": tar_value, "style": style, "price": price, "accId": accId
        })

    def order_target_percent(self, stock, tar_percent, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/order_target_percent', json={
            "stock": stock, "tar_percent": tar_percent, "style": style, "price": price, "accId": accId
        })

    def order_shares(self, stock, shares, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/order_shares', json={
            "stock": stock, "shares": shares, "style": style, "price": price, "accId": accId
        })

    def cancel_order_by_id(self, orderId, accountType='stock'):
        return self._req('POST', '/api/trade/cancel', json={
            "orderId": orderId, "accountType": accountType
        })

    # ============= 期货交易 =============
    def buy_open(self, stock, amount, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/futures/buy_open', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    def buy_close_tdayfirst(self, stock, amount, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/futures/buy_close_tdayfirst', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    def buy_close_ydayfirst(self, stock, amount, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/futures/buy_close_ydayfirst', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    def sell_open(self, stock, amount, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/futures/sell_open', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    def sell_close_tdayfirst(self, stock, amount, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/futures/sell_close_tdayfirst', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    def sell_close_ydayfirst(self, stock, amount, style='LATEST', price=0, accId=''):
        return self._req('POST', '/api/trade/futures/sell_close_ydayfirst', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    # ============= 任务管理 =============
    def cancel_task(self, taskId, accountType='stock'):
        return self._req('POST', '/api/trade/cancel_task', json={
            "taskId": taskId, "accountType": accountType
        })

    def pause_task(self, taskId, accountType='stock'):
        return self._req('POST', '/api/trade/pause_task', json={
            "taskId": taskId, "accountType": accountType
        })

    def resume_task(self, taskId, accountType='stock'):
        return self._req('POST', '/api/trade/resume_task', json={
            "taskId": taskId, "accountType": accountType
        })

    def do_order(self):
        return self._req('POST', '/api/trade/do_order')

    # ============= 账户/订单查询 =============
    def get_trade_detail_data(self, account='stock', datatype='position'):
        return self._req('POST', '/api/trade/trade_detail_data', json={
            "account": account, "datatype": datatype
        })

    def get_value_by_order_id(self, orderId, accountType='stock', datatype='ORDER'):
        return self._req('POST', '/api/trade/value_by_order_id', json={
            "orderId": orderId, "accountType": accountType, "datatype": datatype
        })

    def get_last_order_id(self, account='stock', datatype='ORDER'):
        return self._req('POST', '/api/trade/last_order_id', json={
            "account": account, "datatype": datatype
        })

    def can_cancel_order(self, orderId, accountType='stock'):
        return self._req('POST', '/api/trade/can_cancel_order', json={
            "orderId": orderId, "accountType": accountType
        })

    def get_debt_contract(self, accId=''):
        return self._req('POST', '/api/trade/debt_contract', json={"accId": accId})

    def get_assure_contract(self, accId=''):
        return self._req('POST', '/api/trade/assure_contract', json={"accId": accId})

    def get_enable_short_contract(self, accId=''):
        return self._req('POST', '/api/trade/enable_short_contract', json={"accId": accId})

    def get_ipo_data(self, typ=''):
        return self._req('POST', '/api/trade/ipo_data', json={"type": typ})

    def get_new_purchase_limit(self, accid=''):
        return self._req('POST', '/api/trade/new_purchase_limit', json={"accid": accid})

    def get_smart_algo_param(self, algoList):
        return self._req('POST', '/api/trade/smart_algo_param', json={
            "algoList": algoList if isinstance(algoList, list) else algoList
        })

    def query_credit_account(self, accid='', seq=0):
        return self._req('POST', '/api/trade/query_credit_account', json={
            "accid": accid, "seq": seq
        })

    def query_credit_opvolume(self, accid='', seq=0, optype='', code='', price=0, volume=0):
        return self._req('POST', '/api/trade/query_credit_opvolume', json={
            "accid": accid, "seq": seq, "optype": optype, "code": code,
            "price": price, "volume": volume
        })

    # ============= 引用函数 =============
    def ext_data(self, extdataname, stockcode='', deviation=0):
        return self._req('POST', '/api/ext/ext_data', json={
            "extdataname": extdataname, "stockcode": stockcode, "deviation": deviation
        })

    def ext_data_rank(self, extdataname, stockcode='', deviation=0):
        return self._req('POST', '/api/ext/ext_data_rank', json={
            "extdataname": extdataname, "stockcode": stockcode, "deviation": deviation
        })

    def ext_data_rank_range(self, extdataname, stockcode='', begintime='', endtime=''):
        return self._req('POST', '/api/ext/ext_data_rank_range', json={
            "extdataname": extdataname, "stockcode": stockcode,
            "begintime": begintime, "endtime": endtime
        })

    def ext_data_range(self, extdataname, stockcode='', begintime='', endtime=''):
        return self._req('POST', '/api/ext/ext_data_range', json={
            "extdataname": extdataname, "stockcode": stockcode,
            "begintime": begintime, "endtime": endtime
        })

    def get_factor_value(self, factorname, stockcode='', deviation=0):
        return self._req('POST', '/api/ext/get_factor_value', json={
            "factorname": factorname, "stockcode": stockcode, "deviation": deviation
        })

    def get_factor_rank(self, factorname, stockcode='', deviation=0):
        return self._req('POST', '/api/ext/get_factor_rank', json={
            "factorname": factorname, "stockcode": stockcode, "deviation": deviation
        })

    # ============= 板块管理 =============
    def create_sector(self, parent_node, sector_name, overwrite=True):
        return self._req('POST', '/api/sector/create', json={
            "parent_node": parent_node, "sector_name": sector_name, "overwrite": overwrite
        })

    def create_sector_folder(self, parent_node, folder_name, overwrite=True):
        return self._req('POST', '/api/sector/create_folder', json={
            "parent_node": parent_node, "folder_name": folder_name, "overwrite": overwrite
        })

    def get_sector_list(self, node=''):
        return self._req('POST', '/api/sector/list', json={"node": node})

    def reset_sector_stock_list(self, sector, stock_list):
        return self._req('POST', '/api/sector/reset_stocks', json={
            "sector": sector,
            "stock_list": ','.join(stock_list) if isinstance(stock_list, list) else stock_list
        })

    def add_stock_to_sector(self, sector, stock_code):
        return self._req('POST', '/api/sector/add_stock', json={
            "sector": sector, "stock_code": stock_code
        })

    def remove_stock_from_sector(self, sector, stock_code):
        return self._req('POST', '/api/sector/remove_stock', json={
            "sector": sector, "stock_code": stock_code
        })

    # ============= 兼容方法(原有) =============
    def get_deal(self, account='stock'):
        return self._req('POST', '/api/order/deal', json={"account": account})


# ============= 测试示例 =============
def unit_test():
    client = QMTClient()
    account_type = "stock"  # 根据实际账户调整

    # # 1. 查询资金
    print("[1] 总资金:", client.get_total_money(account_type))
    print("[2] 可用资金:", client.get_available_money(account_type))

    # # 2. 查询持仓
    print("[3] 持仓信息:", json.dumps(client.get_holding(account_type), indent=2, ensure_ascii=False))

    # orders = client.get_order_status()
    # print(orders)

    print("[4] python 版本信息:", client.python_version()) # 返回qmt python 版本信息

    # client.close()

    print("[5] 板块信息:", client.get_sector('000300.SH'))
    print("[6] 行业信息:", client.get_industry('CSRC餐饮业'))
    print("[7] 市场数据信息:", json.dumps(client.get_market_data_ex(['600000.SH', '000001.SZ']), indent=2, ensure_ascii=False))
    print("[8] 最新行情信息:", json.dumps(client.get_full_tick('600000.SH'), indent=2, ensure_ascii=False)) 
    # client.buy_stock("600000.SZ", 6.80, 100)


if __name__ == "__main__":

    unit_test()
