import csv
import time
import random
from datetime import datetime
from statistics import mean
import urllib.request
import json

import requests
from lxml import html

import db
from db import Quarter
from utils import parse_float, parse_int


DAUM_BASIC = 'http://finance.daum.net/item/main.daum?code='
NAVER_COMPANY = 'http://companyinfo.stock.naver.com/v1/company/c1010001.aspx?cmp_cd='
NAVER_YEARLY = "http://companyinfo.stock.naver.com/v1/company/ajax/cF1001.aspx?cmp_cd=%s&fin_typ=0&freq_typ=Y"
NAVER_QUARTERLY = "http://companyinfo.stock.naver.com/v1/company/ajax/cF1001.aspx?cmp_cd=%s&fin_typ=0&freq_typ=Q"
#NAVER_YEARLY_JSON = "http://companyinfo.stock.naver.com/v1/company/cF3002.aspx?cmp_cd=%s&frq=0&rpt=0&finGubun=MAIN&frqTyp=0&cn="
NAVER_JSON1 = 'http://companyinfo.stock.naver.com/v1/company/cF4002.aspx?cmp_cd=%s&frq=0&rpt=1&finGubun=MAIN&frqTyp=0&cn='
LAST_YEAR = str(datetime.now().year - 1)


def fill_company(filename='company.csv'):
    random.seed()
    with open(filename, newline='', encoding='UTF8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            code = row['구글코드']
            if code.startswith('KRX:'):
                code = code[4:]
            elif code.startswith('KOSDAQ:'):
                code = code[7:]
            parse_snowball(code)
            time.sleep(random.random())


def parse_snowball_stocks(filter_bad=True, only_starred_owned=False):
    random.seed()
    find = {'$or': [{'starred': True}, {'owned': True}]} if only_starred_owned else None
    stocks =  db.all_stocks(find=find, filter_bad=filter_bad)
    print('{} 종목 수집'.format(len(stocks)))
    for stock in stocks:
        if stock.get('code', None):
            parse_snowball(stock['code'])
            time.sleep(random.random())
    db.update_ranks()


def tree_from_url(url):
    return html.fromstring(requests.get(url).content)


def parse_basic(code):
    print('종목 {} 기본...'.format(code))
    url = DAUM_BASIC + code
    print('다음 {}'.format(url))
    
    tree = tree_from_url(url)
    if not tree.xpath('//*[@id="topWrap"]/div[1]/h2'):
        return False
    
    title = tree.xpath('//*[@id="topWrap"]/div[1]/h2')[0].text
    price = parse_float(tree.xpath('//*[@id="topWrap"]/div[1]/ul[2]/li[1]/em')[0].text)
    diff = tree.xpath('//*[@id="topWrap"]/div[1]/ul[2]/li[2]/span')[0]
    rate_diff = tree.xpath('//*[@id="topWrap"]/div[1]/ul[2]/li[3]/span')[0].text
    exchange = tree.xpath('//*[@id="topWrap"]/div[1]/ul[1]/li[2]/a')[0].text
    price_diff = parse_float(diff.text)
    rate_diff = float(rate_diff.replace(',', '').replace('+', '').replace('-', '').replace('%', '').replace('％', ''))

    is_price_down = diff.get('class').endswith('down')
    if is_price_down:
        price_diff = -abs(price_diff)
        rate_diff = -abs(rate_diff)
    
    per = parse_float(tree.xpath('//*[@id="stockContent"]/ul[2]/li[3]/dl[2]/dd')[0].text.split('/')[1])
    pbr = parse_float(tree.xpath('//*[@id="stockContent"]/ul[2]/li[4]/dl[2]/dd')[0].text.split('/')[1])
    
    trade_volume = parse_float(tree.xpath('//*[@id="topWrap"]/div[1]/ul[2]/li[5]/span[1]')[0].text)
    trade_value = parse_float(tree.xpath('//*[@id="topWrap"]/div[1]/ul[2]/li[6]/span')[0].text)

    print('종목명: {title} 현재가: {price}'.format(title=title, price=price))

    stock = {
        'code': code,
        'title': title,
        'current_price': price,
        'price_diff': price_diff,
        'rate_diff': rate_diff,
        'per': per,
        'pbr': pbr,
        'trade_volume': trade_volume,
        'trade_value': trade_value,
        'exchange': exchange
    }
    db.save_stock(stock)
    return True


def first_or_none(iter):
    return iter[0] if iter else None


def float_or_none(x):
    return None if not x else float(x.replace(',', ''))


def quarter_from(text):
    if (not text) or ('/' not in text):
        return None
    estimated = text.endswith('(E)')
    text = text[:-3] if estimated else text
    comp = text.split('/')
    return Quarter(year=int(comp[0]), number=int(int(comp[1]) / 3), estimated=estimated)


def parse_quarterly(code):
    print('분기 {}'.format(code))
    url = NAVER_QUARTERLY % (code)
    tree = tree_from_url(url)

    tds = tree.xpath("/html/body/table/tbody/tr[22]/td")
    ROEs = [first_or_none(td.xpath('span/text()')) for td in tds]

    while ROEs and ROEs[-1] is None:
        ROEs.pop()

    if len(ROEs) == 0:
        print('*** 분기 ROE 정보가 없음 >>>')
        return

    ths = tree.xpath("/html/body/table/thead/tr[2]/th")
    quarters = [quarter_from(th.text.strip()) for th in ths]
    
    tds = tree.xpath("/html/body/table/tbody/tr[28]/td")
    BPSs = [first_or_none(td.xpath('span/text()')) for td in tds]
    
    QROEs = list(zip(quarters, ROEs))
    QBPSs = list(zip(quarters, BPSs))

    stock = {
        'code': code,
        'QROEs': QROEs,
        'QBPSs': QBPSs,
    }
    print(stock)
    stock = db.save_stock(stock)
    stock.save_record()

def parse_snowball(code):
    if not parse_basic(code):
        print('수집 실패')
        return
    print('종목 {} 스노우볼...'.format(code))
    url = NAVER_COMPANY + code
    print('네이버 {}'.format(url))
    tree = tree_from_url(url)
    
    bps = parse_int(tree.xpath('//*[@id="pArea"]/div[1]/div/table/tr[3]/td/dl/dt[2]/b')[0].text)
    print('BPS: {}'.format(bps))

    dividend_rate = parse_float(tree.xpath('//*[@id="pArea"]/div[1]/div/table/tr[3]/td/dl/dt[6]/b')[0].text)
    print('배당률: {}'.format(dividend_rate))

    url = NAVER_YEARLY % (code)
    tree = tree_from_url(url)

    try:
        years = list(filter(lambda x: x != '', map(lambda x: x.strip().split('/')[0], tree.xpath('/html/body/table/thead/tr[2]/th/text()'))))
        last_year_index = years.index(LAST_YEAR)
    except ValueError:
        return

    tds = tree.xpath('/html/body/table/tbody/tr[22]/td')
    
    ROEs = [first_or_none(td.xpath('span/text()')) for td in tds]
    while ROEs and ROEs[-1] is None:
        ROEs.pop()
    
    if len(ROEs) == 0:
        print('*** ROE 정보가 없음 >>>')
        return

    CAPEXs = tree.xpath('/html/body/table/tbody/tr[17]/td/span/text()')
    CAPEXs = [parse_float(x) for x in CAPEXs]
    
    ROEs = [float_or_none(x) for x in ROEs]

    DEPTs = tree.xpath('/html/body/table/tbody/tr[24]/td/span/text()')
    DEPTs = [parse_float(x) for x in DEPTs]

    EPSs = tree.xpath('/html/body/table/tbody/tr[26]/td/span/text()')
    EPSs = [parse_float(x) for x in EPSs]

    PERs = tree.xpath('/html/body/table/tbody/tr[27]/td/span/text()')
    PERs = [parse_float(x) for x in PERs]

    BPSs = tree.xpath('/html/body/table/tbody/tr[28]/td/span/text()')
    BPSs = [parse_int(x) for x in BPSs]

    PBRs = tree.xpath('/html/body/table/tbody/tr[29]/td/span/text()')
    PBRs = [parse_float(x) for x in PBRs]

    #자산총계
    TAs = tree.xpath('/html/body/table/tbody/tr[8]/td/span/text()')
    TAs = [parse_int(x) for x in TAs]

    #당기순이익
    NPs = tree.xpath('/html/body/table/tbody/tr[5]/td/span/text()')
    NPs = [parse_int(x) for x in NPs]

    #영업활동현금흐름
    CFOs = tree.xpath('/html/body/table/tbody/tr[14]/td/span/text()')
    CFOs = [parse_int(x) for x in CFOs]
    
    #발행주식수
    TIs = tree.xpath('/html/body/table/tbody/tr[33]/td/span/text()')
    TIs = [parse_int(x) for x in TIs]

    stock = {
        'code': code,
        'dividend_rate': dividend_rate,
        'bps': bps,
        'ROEs': ROEs,
        'last_year_index': last_year_index,
        'PBRs': PBRs,
        'EPSs': EPSs,
        'TAs': TAs,
        'NPs': NPs,
        'CFOs': CFOs,
        'PERs': PERs,
        'TIs': TIs,
        'DEPTs': DEPTs,
        'BPSs': BPSs,
        'CAPEXs': CAPEXs,
    }
    stock = db.save_stock(stock)
    stock.save_record()

    parse_quarterly(code)
    parse_json(code)


def parse_json(code):
    print('종목 {} JSON...'.format(code))
    url = NAVER_JSON1 % (code)
    urlopen = urllib.request.urlopen(url)
    data = json.loads(urlopen.read().decode())
    GPs = []
    if data and 'DATA' in data and data['DATA']:
        yyyy = [int(y[:4]) for y in data['YYMM'] if len(y) > 4 and len(y.split('/')) > 2]
        year_data_keys = {y: i+1 for i, y in enumerate(yyyy)}
    
        for row in data['DATA']:
            if 'ACC_NM' in row and row['ACC_NM'].startswith('매출총이익＜당기'):
                GPs = [(y, row['DATA' + str(year_data_keys[y])]) for y in sorted(list(year_data_keys.keys()))]
                break
    stock = {
        'code': code,
        'GPs': GPs
    }
    print('GPs: {}'.format(GPs))
    stock = db.save_stock(stock)