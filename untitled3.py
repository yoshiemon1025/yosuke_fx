import os
import requests
import pandas as pd
import time
from datetime import datetime

# === Secretsの読み込み ===
API_KEY = os.getenv('EXCHANGERATE_API_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# === URLセットアップ ===
BASE_URL = f'https://v6.exchangerate-api.com/v6/{API_KEY}/pair/USD/JPY'

# === Telegram通知関数 ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"[Telegram通知失敗] {e}")

# === ボリンジャーバンド計算 ===
def calculate_bollinger_bands(df, period=21):
    sma = df['Close'].rolling(window=period).mean()
    std = df['Close'].rolling(window=period).std()
    return {
        '+2σ': sma + 2 * std,
        '+3σ': sma + 3 * std,
        '-2σ': sma - 2 * std,
        '-3σ': sma - 3 * std
    }

# === バンド幅拡大判定 ===
def check_band_expansion(df, lookback=5):
    bands = calculate_bollinger_bands(df)
    widths = bands['+2σ'] - bands['-2σ']
    for i in range(-2, -lookback-2, -1):
        if widths.iloc[i-1] == 0:
            continue
        if widths.iloc[i] / widths.iloc[i-1] >= 1.25:
            continue_expand = all(widths.iloc[j] > widths.iloc[j-1] for j in range(i, 0))
            if continue_expand:
                return True
    return False

# === エントリー判定 ===
def should_notify_entry(df, price):
    if len(df) < 21 or not check_band_expansion(df):
        return None

    bands = calculate_bollinger_bands(df)
    bb_p2 = bands['+2σ'].iloc[-1]
    bb_p3 = bands['+3σ'].iloc[-1]
    bb_m2 = bands['-2σ'].iloc[-1]
    bb_m3 = bands['-3σ'].iloc[-1]

    # 買い条件
    if bb_m3 < price < bb_m2:
        if ((bb_m2 - bb_m3) / 0.25) > (price - bb_m3):
            return 'BUY'

    # 売り条件
    if bb_p2 < price < bb_p3:
        if ((bb_p3 - bb_p2) / 0.75) < (price - bb_p2):
            return 'SELL'

    return None

# === メインループ ===
candles = []

while True:
    now = datetime.now()
    try:
        res = requests.get(BASE_URL)
        price = res.json()['conversion_rate']
    except:
        print(f"[{now}] Price fetch failed")
        time.sleep(60)
        continue

    print(f"[{now}] Current price: {price}")
    candles.append({'time': now, 'Close': price})
    if len(candles) > 200:
        candles.pop(0)

    df = pd.DataFrame(candles)

    signal = should_notify_entry(df, price)
    if signal:
        msg = f"📢 ENTRY SIGNAL: {signal} at {price:.3f} ({now.strftime('%Y-%m-%d %H:%M:%S')})"
        print(msg)
        send_telegram_message(msg)

    time.sleep(60)  # 毎分チェック。実運用では5分でも可
