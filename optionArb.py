import asyncio
import aiohttp
import time
import hmac
import hashlib
from datetime import datetime
from math import floor

bot_token = "" # telegram bot token id
chat_ids = [""] # your telegram id for messages
tickers = ["BTCUSDT", "ETHUSDT", "BNBUSDT"] # assets to tarde
min_pct = 1 # min percentage difference
volume = 100 # your trading order size
leverage = 2 # levarage for using on futures to use less capital for hedging
max_hold = 60*60*24*7 # max time untill option expiration
binance_api_key = "" # binance api key
binance_api_secret = "" # binance secret


async def send_telegram_message(message, chat_id):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"text": message, "chat_id": chat_id}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as response:
                if response.status == 200:
                    return True
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        return False


async def fetch_option_depth(ticker):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://www.binance.com/bapi/eoptions/v1/public/eoptions/market/depth?limit=50&symbol={ticker}') as response:
                data = await response.json()
                return data["data"]
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        return False


async def fetch_depth(session, ticker):
    try:
        url = f'https://www.binance.com/bapi/eoptions/v1/public/eoptions/exchange/tGroup?contract={ticker}'
        async with session.get(url) as response:
            data = await response.json()
            return data["data"]
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        return False


async def fetch_prices(session):
    try:
        url = 'https://fapi.binance.com/fapi/v1/ticker/price'
        async with session.get(url) as response:
            data = await response.json()
            prices = {price['symbol']: float(price['price']) for price in data}
            return prices
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        return False


async def fetch_all_depths(tickers):
    try:
        async with aiohttp.ClientSession() as session:
            tasks = []
            for ticker in tickers:
                task = asyncio.create_task(fetch_depth(session, ticker))
                tasks.append(task)
            depths = await asyncio.gather(*tasks)
            return depths
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        return False


async def open_binance_positions(ticker, option_price, option_qty, futures_qty, side):
    try:
        print(ticker, option_price, option_qty, futures_qty, side)
        data_options = {
            "symbol": ticker,
            "price": str(option_price),
            "quantity": str(option_qty),
            "side": "BUY",
            "type": "LIMIT",
            "timestamp": str(int(time.time()) * 1000),
            "recvWindow": "10000000",
        }
        query_string_options = "&".join(
            [f"{k}={v}" for k, v in data_options.items()])
        signature_options = hmac.new(
            binance_api_secret.encode("utf-8"),
            query_string_options.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        headers = {
            "X-MBX-APIKEY": binance_api_key
        }
        data_options["signature"] = signature_options
        data_futures = {
            "symbol": ticker.split("-")[0]+"USDT",
            "quantity": str(futures_qty),
            "side": side,
            "type": "MARKET",
            "timestamp": str(int(time.time())*1000),
            "recvWindow": "10000000",
        }
        query_string_futures = "&".join(
            [f"{k}={v}" for k, v in data_futures.items()])
        signature_futures = hmac.new(
            binance_api_secret.encode("utf-8"),
            query_string_futures.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        data_futures["signature"] = signature_futures
        data_leverage = {
            "symbol": ticker.split("-")[0]+"USDT",
            "leverage": str(leverage),
            "timestamp": str(int(time.time())*1000),
            "recvWindow": "10000000",
        }
        query_string_leverage = "&".join(
            [f"{k}={v}" for k, v in data_leverage.items()])
        signature_leverage = hmac.new(
            binance_api_secret.encode("utf-8"),
            query_string_leverage.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        data_leverage["signature"] = signature_leverage
        async with aiohttp.ClientSession() as session:
            await session.post("https://fapi.binance.com/fapi/v1/leverage", headers=headers, params=data_leverage)
            async with session.post(f"https://fapi.binance.com/fapi/v1/order", headers=headers, params=data_futures) as response1:
                res1 = await response1.json()
                print(res1)
                if res1["orderId"]:
                    async with session.post(f"https://eapi.binance.com/eapi/v1/order", headers=headers, params=data_options) as response2:
                        res2 = await response2.json()
                        print(res2)
                        if res2["orderId"]:
                            return True
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        return False


async def main():
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                depths = await fetch_all_depths(tickers)
                prices = await fetch_prices(session)
                current_time = int(time.time())
                if depths and prices:
                    for data in depths:
                        for date_option in data:
                            expiration_time = int(
                                date_option["expirationTime"]/1000)
                            if expiration_time < current_time + max_hold:
                                for option_price in date_option["optionPriceList"]:
                                    if option_price["call"] and option_price["call"]["askPrice"] != 0 and option_price["expirationPrice"] < prices[option_price["call"]["symbol"].split("-")[0]+"USDT"]:
                                        diff = (prices[option_price["call"]["symbol"].split("-")[0]+"USDT"] - (option_price["expirationPrice"] +
                                                option_price["call"]["askPrice"])) / prices[option_price["call"]["symbol"].split("-")[0]+"USDT"] * 100
                                        if diff > min_pct:
                                            option_depth = await fetch_option_depth(option_price["call"]["symbol"])
                                            if float(option_price["call"]["askPrice"]) == float(option_depth["asks"][0]["price"]):
                                                avb_qty = float(
                                                    option_depth["asks"][0]["quote"])
                                                if avb_qty*option_price["expirationPrice"] > volume:
                                                    pos_qty = floor(volume /
                                                                    prices[option_price["call"]["symbol"].split(
                                                                        "-")[0]+"USDT"]*100)/100
                                                    if pos_qty >= 0.01:
                                                        pos = await open_binance_positions(option_price["call"]["symbol"], float(option_depth["asks"][0]["price"]), pos_qty, pos_qty, "SELL")
                                                        for chat_id in chat_ids:
                                                            await send_telegram_message(f'Ticker: {option_price["call"]["symbol"]}\nStrike : {option_price["expirationPrice"]}\nPrice : {option_price["call"]["askPrice"]}\nAvailable qty: {avb_qty}\nUnderlying price: {prices[option_price["call"]["symbol"].split("-")[0]+"USDT"]}\nDifference: {diff:.2}%', chat_id)
                                    elif option_price["put"] and option_price["put"]["askPrice"] != 0 and option_price["expirationPrice"] > prices[option_price["put"]["symbol"].split("-")[0]+"USDT"]:
                                        diff = ((option_price["expirationPrice"] - option_price["put"]["askPrice"]) - prices[option_price["put"]["symbol"].split(
                                            "-")[0]+"USDT"]) / prices[option_price["put"]["symbol"].split("-")[0]+"USDT"] * 100
                                        if diff > min_pct:
                                            option_depth = await fetch_option_depth(option_price["put"]["symbol"])
                                            if float(option_price["put"]["askPrice"]) == float(option_depth["asks"][0]["price"]):
                                                avb_qty = float(
                                                    option_depth["asks"][0]["quote"])
                                                if avb_qty*option_price["expirationPrice"] > volume:
                                                    pos_qty = floor(volume /
                                                                    prices[option_price["put"]["symbol"].split(
                                                                        "-")[0]+"USDT"]*100)/100
                                                    if pos_qty >= 0.01:
                                                        pos = await open_binance_positions(option_price["put"]["symbol"], float(option_depth["asks"][0]["price"]), pos_qty, pos_qty, "BUY")
                                                        for chat_id in chat_ids:
                                                            await send_telegram_message(f'Ticker: {option_price["put"]["symbol"]}\nStrike : {option_price["expirationPrice"]}\nPrice : {option_price["put"]["askPrice"]}\nAvailable qty: {avb_qty}\nUnderlying price: {prices[option_price["put"]["symbol"].split("-")[0]+"USDT"]}\nDifference: {diff:.2}%', chat_id)
        except Exception as e:
            print(e)
            continue

asyncio.run(main())
