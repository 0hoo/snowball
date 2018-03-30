from typing import Tuple, List

from datetime import datetime
from statistics import mean
from collections import UserDict, namedtuple

from pymongo import MongoClient, ASCENDING, DESCENDING


FScore = namedtuple('FScore', ['total_issued_stock', 'profitable', 'cfo'])


YEAR_STAT = Tuple[int, int]
YEAR_FSCORE = Tuple[int, FScore]


client = MongoClient()
db = client.snowball


DIVIDEND_TAX_RATE = 15.40
FUTURE = 10
TARGET_RATE = 15
LAST_YEAR = datetime.now().year - 1


class Stock(UserDict):
    @property
    def object_id(self) -> str:
        return self['_id']

    @property
    def price_arrow(self) -> str:
        if self.get('price_diff') == 0:
            return ''
        else:
            return '▲' if self.get('price_diff') > 0 else '▼'

    @property
    def price_color(self) -> str:
        if self.get('price_diff') == 0:
            return 'black'
        else:
            return 'red' if self.get('price_diff') > 0 else 'blue'

    @property
    def price_sign(self) -> str:
        return '+' if self.get('price_diff') > 0 else ''

    @property
    def financial_statements_url(self) -> str:
        return "http://companyinfo.stock.naver.com/v1/company/ajax/cF1001.aspx?cmp_cd=%s&fin_typ=0&freq_typ=Y" % (self['code'])

    @property
    def roes(self) -> List[Tuple[int, int]]:
        return self.year_stat('ROEs')

    @property
    def pbrs(self) -> List[Tuple[int, int]]:
        return self.year_stat('PBRs')

    @property
    def pers(self) -> List[Tuple[int, int]]:
        return self.year_stat('PERs')

    @property
    def epss(self) -> List[Tuple[int, int]]:
        return self.year_stat('EPSs')

    @property
    def low_pbr(self) -> float:
        return min([year_pbr[1] for year_pbr in self.year_stat('PBRs', exclude_future=True)])

    @property
    def high_pbr(self) -> float:
        return max([year_pbr[1] for year_pbr in self.year_stat('PBRs', exclude_future=True)])

    @property
    def mid_pbr(self) -> float:
        return (self.low_pbr + self.get('pbr')) / 2
    
    @property
    def adjusted_eps(self) -> int:
        if (not ('EPSs' in self)) or len(self['EPSs']) < 3:
            return 0
        last_year_index = self['last_year_index']
        past_eps = self['EPSs'][0:last_year_index+1]
        if len(past_eps) < 3:
            return 0
        return int(((past_eps[-1] * 3) + (past_eps[-2] * 2) + past_eps[-3]) / 6)

    @property
    def roe_max_diff(self) -> float:
        ROEs = self.get('ROEs', [])
        return max(ROEs) - min(ROEs) if len(ROEs) > 2 else 0

    @property
    def mid_roe(self) -> float:
        ROEs = self.get('ROEs', [])
        return mean([mean(ROEs), min(ROEs)]) if len(ROEs) > 2 else 0    

    @property
    def eps_growth(self) -> float:
        EPSs = self.get('EPSs', [])
        try:
            return mean([y/x - 1 for x, y in zip(EPSs[:-1], EPSs[1:])]) * 100
        except ZeroDivisionError:
            return 0

    @property
    def has_note(self) -> bool:
        return len(self.get('note', '')) > 0

    @property
    def latest_fscore(self) -> int:
        return sum([
            self.get('fscore_total_issued_stock', 0), 
            self.get('fscore_profitable', 0), 
            self.get('fscore_cfo', 0)])

    @property
    def fscores(self) -> List[Tuple[int, FScore]]:
        NPs = self.year_stat('NPs')
        return [(np[0], self.fscore(np[0])) for np in NPs]

    @property
    def mean_per(self) -> float:
        PERs = self.get('PERs', [])
        return mean(PERs) if len(PERs) > 2 else 0

    @property
    def expected_rate_by_adjusted_future_pbr(self) -> float:
        current_price = self.get('current_price', 0)
        return ((self.calc_future_price_adjusted_future_pbr(FUTURE) / float(current_price)) ** (1.0 / FUTURE) - 1) * 100        

    def calc_future_bps(self, future) -> int:
        future_roe = self.get('future_roe', 0)
        bps = self.get('bps', 0)
        adjusted_future_roe = self.get('adjusted_future_roe', 0)
        if adjusted_future_roe > 0:
            future_roe = adjusted_future_roe
        return int(bps * ((1 + (1 * future_roe / 100)) ** future))

    def calc_future_price_low_pbr(self, future) -> int:
        return int(self.calc_future_bps(future) * self.low_pbr)

    def calc_future_price_high_pbr(self, future) -> int:
        return int(self.calc_future_bps(future) * self.high_pbr)

    def calc_future_price_current_pbr(self, future) -> int:
        return int(self.calc_future_bps(future) * self['pbr'])

    def calc_future_price_low_current_mid_pbr(self, future) -> int:
        return int(self.calc_future_bps(future) * self.mid_pbr)

    def calc_future_price_adjusted_future_pbr(self, future) -> int:
        return int(self.calc_future_bps(future) * self.get('adjusted_future_pbr', 0))

    def fscore(self, year) -> FScore:
        total_issued_stock = 0
        profitable = 0
        cfo = 0

        TIs = self.get('TIs', [])
        if len(TIs) > 2 and len(set(TIs)) <= 1:
            total_issued_stock = 1
        NPs = self.year_stat('NPs')
        year_profit = [p[1] for p in NPs if p[0] == year]
        if len(year_profit) > 0 and year_profit[0] > 0:
            profitable = 1
        CFOs = self.year_stat('CFOs')
        year_cfo = [c[1] for c in CFOs if c[0] == year]
        if len(year_cfo) > 0 and year_cfo[0] > 0:
            cfo = 1
        
        return FScore(total_issued_stock=total_issued_stock, profitable=profitable, cfo=cfo)

    def fill_snowball_stat(self):
        code = self.get('code')
        bps = self.get('bps', 0)
        current_price = self.get('current_price', 0)
        ROEs = self.get('ROEs')
        if not ROEs:
            print('기업정보 없는 종목: {}'.format(self.get('title')))
            return
        last_four_years_roe = self.get('last_four_years_roe')
        dividend_rate = self.get('dividend_rate', 0)

        #배당소득세 조정 배당률
        tax_adjust = dividend_rate * (DIVIDEND_TAX_RATE / 100)
        #4년 평균 ROE
        mean_roe = mean(last_four_years_roe)
        #기대 ROE
        future_roe = mean_roe - tax_adjust
        self['future_roe'] = future_roe
        #미래 BPS        
        future_bps = self.calc_future_bps(FUTURE)
        #연평균 기대수익률
        expected_rate = ((future_bps / float(current_price)) ** (1.0 / FUTURE) - 1) * 100
        #투자가능가격
        invest_price = int(future_bps / ((1 + (1 * TARGET_RATE / 100)) ** FUTURE))

        #최고/중간/최저PBR 기준 수익률
        expected_rate_by_current_pbr = ((self.calc_future_price_current_pbr(FUTURE) / float(current_price)) ** (1.0 / FUTURE) - 1) * 100
        expected_rate_by_mid_pbr = ((self.calc_future_price_low_current_mid_pbr(FUTURE) / float(current_price)) ** (1.0 / FUTURE) - 1) * 100
        try:
            expected_rate_by_low_pbr = float(((self.calc_future_price_low_pbr(FUTURE) / float(current_price)) ** (1.0 / FUTURE) - 1) * 100)
        except:
            expected_rate_by_low_pbr = 0

        #숙향 내재가치와 할인률
        intrinsic_value = int((bps + (self.adjusted_eps * 10)) / 2)
        intrinsic_discount_rate = (intrinsic_value / current_price ** (1.0 / 1) - 1) * 100

        #PEG
        peg_current_per = self.get('per', 0) / self.eps_growth if self.eps_growth != 0 else 0
        peg_mean_per = self.mean_per / self.eps_growth if self.eps_growth != 0 else 0

        #최근 FScore
        fscore = self.fscores[-1][1]

        stock = {
            'code': code,
            'mean_roe': mean_roe,
            'future_roe': future_roe,
            'future_bps': future_bps,
            'expected_rate': expected_rate,
            'invest_price': invest_price,
            'expected_rate_by_current_pbr': expected_rate_by_current_pbr,
            'expected_rate_by_mid_pbr': expected_rate_by_mid_pbr,
            'expected_rate_by_low_pbr': expected_rate_by_low_pbr,
            'intrinsic_value': intrinsic_value,
            'intrinsic_discount_rate': intrinsic_discount_rate,
            'peg_current_per': peg_current_per,
            'peg_mean_per': peg_mean_per,
            'fscore_total_issued_stock': fscore.total_issued_stock,
            'fscore_profitable': fscore.profitable,
            'fscore_cfo': fscore.cfo,   
        }
        save_stock(stock)

    def year_stat(self, stat, exclude_future=False) -> List[Tuple[int, int]]:
        stats = self.get(stat)
        if not stats:
            return [(0, 0)]
        last_year_index = self.get('last_year_index')
        year = lambda idx: LAST_YEAR - (last_year_index - idx)
        return [(year(idx), value) for idx, value in enumerate(stats) 
            if not exclude_future or year(idx) <= LAST_YEAR]

    def __str__(self) -> str:
        return '{} : {}'.format(self['title'], self['code'])


def all_stocks(order_by='title', ordering='asc', find=None) -> List[Stock]:
    if find:
        stocks = db.stocks.find(find).sort(order_by, ASCENDING if ordering == 'asc' else DESCENDING)
    else:
        stocks = db.stocks.find().sort(order_by, ASCENDING if ordering == 'asc' else DESCENDING)
    return [Stock(s) for s in stocks]


def stock_by_code(code) -> Stock:
    return Stock(db.stocks.find_one({'code': code}))


def save_stock(stock) -> Stock:
    exist = db.stocks.find_one({'code': stock['code']})
    if exist:
        print("update:" ,stock)
        db.stocks.update_one({'code': exist['code']}, {'$set': stock})
    else:
        db.stocks.insert_one(stock)
    return stock_by_code(stock['code'])