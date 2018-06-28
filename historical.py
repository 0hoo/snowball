from typing import List, Optional, Tuple
from datetime import datetime
from collections import namedtuple
from statistics import mean
import itertools
import pandas as pd

import fix_yahoo_finance as yf

from db import Stock


yf.pdr_override()


now = datetime.now()
THIS_YEAR = now.year
TODAY = now.strftime('%Y-%m-%d')
TWO_YEARS_AGO = now.replace(year=now.year-2, month=1, day=1).strftime('%Y-%m-%d')


Record = namedtuple('Record', ['date', 'price', 'expected_rate', 'bps', 'fROE'])
YearStat = namedtuple('YearStat', ['year', 'high_price', 'low_price', 'high_expected_rate', 'low_expected_rate', 'bps', 'fROE'])
Event = namedtuple('Event', ['date', 'record', 'buy'])
EventStat = namedtuple('EventStat', ['buy_count', 'sell_count', 'profit'])


def make_record(date, price, bps, stock) -> Record:
    if not bps:
        return Record(date=date, price=price, expected_rate=0, bps=0, fROE=0) 
    year = date.year
    ROEs = [roe[1] for roe in stock.four_years_roe(year)]
    if len(ROEs) < 1:
        return Record(date=date, price=price, expected_rate=0, bps=0, fROE=0) 

    future_roe = mean(ROEs)
    calc_future_bps = lambda future: int(bps * ((1 + (1 * future_roe / 100)) ** future))
    expected_rate = stock.calc_expected_rate(calc_future_bps, 10, price)
    return Record(date=date, price=price, expected_rate=expected_rate, bps=bps, fROE=future_roe)    


def records_by_yahoo(stock: Stock) -> List[Record]:
    exchange = stock.get('exchange', '')
    yahoo_code = str(stock['code']) + ('.KS' if exchange == '코스피' else '.KQ')
    yahoo_prices = yf.download(yahoo_code, start=TWO_YEARS_AGO, end=TODAY)
    print(yahoo_prices)
    keys = yahoo_prices.reset_index()['Date'].tolist()
    values = yahoo_prices['Close'].tolist()
    prices = [(pd.to_datetime(p[0]), p[1]) for p in zip(keys, values)]
    BPSs = {b[0]: b[1] for b in stock.year_stat('BPSs', exclude_future=True)}

    return [make_record(p[0], p[1], BPSs.get(p[0].year-1), stock) for p in prices]


def make_year_stat(year: int, records: List[Record]) -> YearStat:
    high_price = max(record.price for record in records)
    low_price = min(record.price for record in records)
    high_expected_rate = max(record.expected_rate for record in records)
    low_expected_rate = min(record.expected_rate for record in records)
    stat = YearStat(year=year, 
            high_price=high_price, low_price=low_price, 
            high_expected_rate=high_expected_rate, low_expected_rate=low_expected_rate,
            bps=records[0].bps, fROE=records[0].fROE)
    return stat


def records_by_year(stock: Stock) -> List[Tuple[YearStat, List[Record]]]:
    records = records_by_yahoo(stock)
    by_year = [(k, list(list(g))) for k, g in itertools.groupby(records, lambda r: r.date.year)]
    by_year = [(make_year_stat(year, records), records) for year, records in by_year]
    events = simulate(by_year)
    return [(year_stat, records, [e for e in events if e.date.year == year_stat.year]) for year_stat, records in by_year]


def simulate(by_year: List[Tuple[YearStat, List[Record]]]) -> List[Event]:
    events = []
    last_buy_event = None
    for year_stat, records in by_year:
        mid_expected_rate = mean([year_stat.high_expected_rate, year_stat.low_expected_rate])
        if mid_expected_rate < 13.5:
            mid_expected_rate = 13.5
        for r in records:
            if not last_buy_event and r.expected_rate >= mid_expected_rate:
                last_buy_event = Event(date=r.date, record=r, buy=True)
                events.append(last_buy_event)
            if last_buy_event and ((last_buy_event.record.expected_rate - r.expected_rate) >= 1.2
                or (last_buy_event.record.price * 0.13 + last_buy_event.record.price) <= r.price):
                events.append(Event(date=r.date, record=r, buy=False))
                last_buy_event = None
    return events
