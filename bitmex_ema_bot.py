#!/usr/bin/python3
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import time
import ccxt
import sys

LOT = 100
CLOSE_RANGE = 30
STOP_RANGE = 20

# api・シークレットキーを記入
bitmex = ccxt.bitmex({
    'apiKey': 'xxxxxxxxxx',
    'secret': 'xxxxxxxxxx',
})
# testnetで使用する場合は下記コメントアウトを外す
# bitmex.urls['api'] = bitmex.urls['test']

def limit(side, price, size):
    return bitmex.create_order('BTC/USD', type='limit', side=side, price=price, amount=size)

def market(side, size):
    return bitmex.create_order('BTC/USD', type='market', side=side, amount=size)

# dataframe for executions
df = pd.DataFrame(columns=['exectime', 
                           'open', 
                           'high', 
                           'low', 
                           'close', 
                           'price', 
                           'volume'])

#ローソク足の時間を指定
periods = ["60"]

# after以降のデータを取得(after = 10分前)
after = (datetime.now() - timedelta(minutes=10)).strftime('%s')

#クエリパラメータを指定    
query = {"periods":','.join(periods)}
query['after'] = ''.join(after)

def get_ema():
    #ローソク足取得
    result = json.loads(requests.get("https://api.cryptowat.ch/markets/bitmex/btcusd-perpetual-futures/ohlc",params=query).text)["result"]

    # add to dataframe
    for period in periods:
        row = result[period]
        df = pd.DataFrame(row,
                          columns=['exectime', 
                                   'open', 
                                   'high', 
                                   'low', 
                                    'close', 
                                   'price', 
                                   'volume'])
        
    # 平滑化係数(0~1を指定、1に近いほど現在の価格比重が重くなる)
    alpha = 0.15
    # emaの計算 ※pandasバージョン0.18.0以上
    ema = df['close'].ewm(alpha=alpha).mean()[-1:]
    # print("ema: %s" % ema)
    return ema


entryPrice = 0
openId = ''
closeId = ''
# while
while True:
    try:
        print("==========")
        print("entryPrice: " + str(entryPrice))
        print("openId: " + str(openId))
        print("closeId: " + str(closeId))
        last = bitmex.fetch_ticker('BTC/USD')['last']
        print('last price: ' + str(last))
    
        open_orders = bitmex.fetch_open_orders()
        position = bitmex.private_get_position()
        # if Active Orderがない場合
        if open_orders == []:
            # if ポジションを持っていない場合
            if position == [] or position[0]['currentQty'] == 0:
                print('No Position')
                ema = get_ema().values[0]
                print("ema: " + str(ema))
                # if 最後の約定価格がemaより高い
                if last >= ema:
                    # 買いポジションでエントリー
                    entryPrice = last - 2
                    order = limit('buy', entryPrice, LOT)
                    print("buy entry")
                    openId = order['id']

            # elif 買いポジションを持っている場合
            elif position[0]['currentQty'] >= LOT:
                # エントリーポイント + CLOSE_RANGE で指値
                order = limit('sell', entryPrice + CLOSE_RANGE, LOT)
                print('position close')
                closeId = order['id']
        
        # if エントリーポイント - STOP_RANGE なら損切り
        if position[0]['currentQty'] >= LOT and last <= (entryPrice - STOP_RANGE):
            market('sell', LOT)
            print('loss cut')
            order = bitmex.cancel_order(closeId)
            print('order cancel')
    
        # if エントリー注文を出して1分以上経過した場合、注文を取り消す
        if open_orders != [] and open_orders[0]['id'] == openId and datetime.now() - timedelta(minutes=1) > datetime.fromtimestamp(int(str(open_orders[0]['timestamp'])[0:10])):
            cancel = bitmex.cancel_order(openId)
            print("order cancel")
            
    except Exception as e:
        print("error: {0}".format(e))

    time.sleep(10)
