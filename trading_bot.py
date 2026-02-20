#!/usr/bin/env python3
"""간단한 이동평균 교차 기반 자동매매(페이퍼 트레이딩) 예제."""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List


@dataclass
class Candle:
    close_time: int
    close: float


def fetch_klines(symbol: str, interval: str, limit: int = 200) -> List[Candle]:
    """Binance 퍼블릭 API에서 캔들 데이터를 가져온다."""
    query = urllib.parse.urlencode({"symbol": symbol.upper(), "interval": interval, "limit": limit})
    url = f"https://api.binance.com/api/v3/klines?{query}"
    with urllib.request.urlopen(url, timeout=10) as response:
        rows = json.loads(response.read().decode("utf-8"))

    return [Candle(close_time=int(row[6]), close=float(row[4])) for row in rows]


def sma(values: List[float], period: int) -> float:
    if len(values) < period:
        raise ValueError(f"데이터 길이({len(values)})가 기간({period})보다 짧습니다.")
    return sum(values[-period:]) / period


@dataclass
class PaperAccount:
    cash: float
    coin: float = 0.0

    def buy_all(self, price: float) -> None:
        if self.cash <= 0:
            return
        self.coin += self.cash / price
        self.cash = 0.0

    def sell_all(self, price: float) -> None:
        if self.coin <= 0:
            return
        self.cash += self.coin * price
        self.coin = 0.0

    def total_value(self, price: float) -> float:
        return self.cash + self.coin * price


def signal(prices: List[float], short_period: int, long_period: int) -> str:
    """이동평균 골든/데드 크로스 기반 시그널 생성."""
    if short_period >= long_period:
        raise ValueError("short 기간은 long 기간보다 작아야 합니다.")

    if len(prices) < long_period + 1:
        return "HOLD"

    prev_short = sma(prices[:-1], short_period)
    prev_long = sma(prices[:-1], long_period)
    curr_short = sma(prices, short_period)
    curr_long = sma(prices, long_period)

    if prev_short <= prev_long and curr_short > curr_long:
        return "BUY"
    if prev_short >= prev_long and curr_short < curr_long:
        return "SELL"
    return "HOLD"


def now_kst() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def run_bot(symbol: str, interval: str, short_period: int, long_period: int, initial_cash: float, poll_seconds: int) -> None:
    account = PaperAccount(cash=initial_cash)
    print("⚠️ 실계좌 주문은 포함되지 않은 페이퍼 트레이딩 예제입니다.")

    while True:
        candles = fetch_klines(symbol=symbol, interval=interval, limit=max(200, long_period + 5))
        prices = [c.close for c in candles]
        last_price = prices[-1]

        decision = signal(prices, short_period=short_period, long_period=long_period)
        if decision == "BUY":
            account.buy_all(last_price)
        elif decision == "SELL":
            account.sell_all(last_price)

        print(
            f"[{now_kst()}] {symbol} {interval} price={last_price:.4f} "
            f"signal={decision:>4} cash={account.cash:.2f} coin={account.coin:.6f} "
            f"total={account.total_value(last_price):.2f}"
        )

        time.sleep(poll_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="이동평균 교차 기반 자동매매(페이퍼 트레이딩) 봇")
    parser.add_argument("--symbol", default="BTCUSDT", help="거래 심볼 (기본값: BTCUSDT)")
    parser.add_argument("--interval", default="1m", help="캔들 주기 (기본값: 1m)")
    parser.add_argument("--short", type=int, default=7, help="단기 이동평균 기간")
    parser.add_argument("--long", type=int, default=25, help="장기 이동평균 기간")
    parser.add_argument("--cash", type=float, default=1_000_000.0, help="초기 원화/달러 가정 자산")
    parser.add_argument("--poll", type=int, default=20, help="조회 간격(초)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_bot(
        symbol=args.symbol,
        interval=args.interval,
        short_period=args.short,
        long_period=args.long,
        initial_cash=args.cash,
        poll_seconds=args.poll,
    )
