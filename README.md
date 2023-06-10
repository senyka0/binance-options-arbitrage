# binance-options-arbitrage
Script for trade arbitrage opportunities between European-style options and Perpetual futures, with notifications in telegram

## To run
### 1. Install requirements:
```sh
pip install -r requirements.txt
```
### 2. Set your keys and parameters
```sh
bot_token = "" # telegram bot token id
chat_ids = [""] # your telegram id for messages
tickers = ["BTCUSDT", "ETHUSDT", "BNBUSDT"] # assets to tarde
min_pct = 1 # min percentage difference
volume = 100 # your trading order size
leverage = 2 # levarage for using on futures to use less capital for hedging
max_hold = 60*60*24*7 # max time untill option expiration
binance_api_key = "" # binance api key
binance_api_secret = "" # binance secret
```
### 3. Start app
```sh
python3 optionArb.py
