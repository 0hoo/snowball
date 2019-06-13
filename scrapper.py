from typing import List
import csv
import time
import random
from datetime import datetime
from statistics import mean
import urllib.request
import json
import codecs
from functools import partial

import requests
from lxml import html

import db
from db import Quarter
from utils import parse_float, parse_int, first_or_none, float_or_none


DAUM_BASIC = 'http://finance-service.daum.net/item/main.daum?code='
NAVER_COMPANY = 'http://companyinfo.stock.naver.com/v1/company/c1010001.aspx?cmp_cd='
NAVER_YEARLY = "http://companyinfo.stock.naver.com/v1/company/ajax/cF1001.aspx?cmp_cd=%s&fin_typ=0&freq_typ=Y"
NAVER_QUARTERLY = "http://companyinfo.stock.naver.com/v1/company/ajax/cF1001.aspx?cmp_cd=%s&fin_typ=0&freq_typ=Q"
NAVER_JSON1 = 'http://companyinfo.stock.naver.com/v1/company/cF4002.aspx?cmp_cd=%s&frq=0&rpt=1&finGubun=MAIN&frqTyp=0&cn='
NAVER_JSON5 = 'http://companyinfo.stock.naver.com/v1/company/cF4002.aspx?cmp_cd=%s&frq=0&rpt=5&finGubun=MAIN&frqTyp=0&cn='
NAVER = 'https://finance.naver.com/item/main.nhn?code='
FNGUIDE = 'http://comp.fnguide.com/SVO2/ASP/SVD_main.asp?pGB=1&gicode=A'
FNGUIDE_FINANCIAL_STMT = 'http://comp.fnguide.com/SVO2/ASP/SVD_Finance.asp?pGB=1&gicode=A%s&cID=&MenuYn=Y&ReportGB=&NewMenuID=103'
FNGUIDE_FINANCIAL_RATIO = 'http://comp.fnguide.com/SVO2/ASP/SVD_FinanceRatio.asp?pGB=1&gicode=A%s&cID=&MenuYn=Y&ReportGB=&NewMenuID=104'
FNGUIDE_INVEST_GUIDE = 'http://comp.fnguide.com/SVO2/asp/SVD_Invest.asp?pGB=1&gicode=A%s&cID=&MenuYn=Y&ReportGB=&NewMenuID=105&stkGb=701'

LAST_YEAR = str(datetime.now().year - 1)


def fill_company(filename: str='company.csv'):
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
    db.update_ranks()


def parse_snowball_stocks(filter_bad: bool=True, only_starred_owned: bool=False):
    random.seed()
    find = {'$or': [{'starred': True}, {'owned': True}]} if only_starred_owned else None
    stocks =  db.all_stocks(find=find, filter_bad=filter_bad)
    print('{} 종목 수집'.format(len(stocks)))
    for stock in stocks:
        if stock.get('code', None):
            parse_snowball(stock['code'])
            time.sleep(random.random())
    db.update_ranks()


def tree_from_url(url: str, decode: str=None):
    content = requests.get(url).content
    if decode:
        content = content.decode(decode)
    return html.fromstring(content)


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

    agg_value = parse_float(tree.xpath('//*[@id="stockContent"]/ul[2]/li[2]/dl[2]/dd')[0].text)

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
        'exchange': exchange,
        'agg_value': agg_value,
    }
    db.save_stock(stock)
    return True


def quarter_from(text: str) -> Quarter:
    if (not text) or ('/' not in text):
        return None
    estimated = text.endswith('(E)')
    text = text[:-3] if estimated else text
    comp = text.split('/')
    return Quarter(year=int(comp[0]), number=int(int(comp[1]) / 3), estimated=estimated)


def parse_quarterly(code: str):
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
    stock = db.save_stock(stock)


def parse_naver_company(code: str):
    url = NAVER_COMPANY + code
    print('네이버 {}'.format(url))
    tree = tree_from_url(url)
    
    element = tree.xpath('//*[@id="pArea"]/div[1]/div/table/tr[3]/td/dl/dt[2]/b')
    if not element:
        print('수집 실패')
        return False
    bps = parse_int(element[0].text)
    print('BPS: {}'.format(bps))

    element = tree.xpath('//*[@id="pArea"]/div[1]/div/table/tr[3]/td/dl/dt[6]/b')
    if element:
        dividend_rate = parse_float(element[0].text)
        print('배당률: {}'.format(dividend_rate))
    else:
        dividend_rate = 0
        print('배당 수집 실패')
        return False
    
    stock = {
        'code': code,
        'bps': bps,
        'dividend_rate': dividend_rate,
        'use_fnguide': False,
    }
    stock = db.save_stock(stock)
    return stock


def parse_snowball(code: str):
    if not parse_basic(code):
        print('수집 실패')
        return

    if parse_fnguide(code):
        parse_fnguide_financial_statements(code)
        parse_fnguide_financial_ratio(code)
        parse_fnguide_invest_guide(code)
    else:
        print('FnGuide 수집실패')
        if not parse_naver_company(code):
            return
    
    # print('종목 {} 스노우볼...'.format(code))
    
    # url = NAVER_YEARLY % (code)
    # print(url)
    # tree = tree_from_url(url)

    # try:
    #     years = list(filter(lambda x: x != '', map(lambda x: x.strip().split('/')[0], tree.xpath('/html/body/table/thead/tr[2]/th/text()'))))
    #     last_year_index = years.index(LAST_YEAR)
    # except ValueError:
    #     return

    # tds = tree.xpath('/html/body/table/tbody/tr[22]/td')
    
    # ROEs = [first_or_none(td.xpath('span/text()')) for td in tds]
    # while ROEs and ROEs[-1] is None:
    #     ROEs.pop()
    
    # if len(ROEs) == 0:
    #     print('*** ROE 정보가 없음 >>>')
    #     return
    
    # ROEs = [float_or_none(x) for x in ROEs]

    # DEPTs = tree.xpath('/html/body/table/tbody/tr[24]/td/span/text()')
    # DEPTs = [parse_float(x) for x in DEPTs]

    # EPSs = tree.xpath('/html/body/table/tbody/tr[26]/td/span/text()')
    # EPSs = [parse_float(x) for x in EPSs]

    # PERs = tree.xpath('/html/body/table/tbody/tr[27]/td/span/text()')
    # PERs = [parse_float(x) for x in PERs]

    # BPSs = tree.xpath('/html/body/table/tbody/tr[28]/td/span/text()')
    # BPSs = [parse_int(x) for x in BPSs]

    # PBRs = tree.xpath('/html/body/table/tbody/tr[29]/td/span/text()')
    # PBRs = [parse_float(x) for x in PBRs]

    # #자산총계
    # TAs = tree.xpath('/html/body/table/tbody/tr[8]/td/span/text()')
    # TAs = [parse_int(x) for x in TAs]

    # #당기순이익
    # NPs = tree.xpath('/html/body/table/tbody/tr[5]/td/span/text()')
    # NPs = [parse_int(x) for x in NPs]

    # #영업활동현금흐름
    # CFOs = tree.xpath('/html/body/table/tbody/tr[14]/td/span/text()')
    # CFOs = [parse_int(x) for x in CFOs]

    # #투자활동현금흐름
    # CFIs = tree.xpath('/html/body/table/tbody/tr[15]/td/span/text()')
    # CFIs = [parse_int(x) for x in CFIs]

    # #투자활동현금흐름
    # CFFs = tree.xpath('/html/body/table/tbody/tr[16]/td/span/text()')
    # CFFs = [parse_int(x) for x in CFFs]

    # CAPEXs = tree.xpath('/html/body/table/tbody/tr[17]/td/span/text()')
    # CAPEXs = [parse_float(x) for x in CAPEXs]

    # #잉여현금흐름
    # FCFs = tree.xpath('/html/body/table/tbody/tr[18]/td/span/text()')
    # FCFs = [parse_int(x) for x in FCFs]
    
    # #발행주식수
    # TIs = tree.xpath('/html/body/table/tbody/tr[33]/td/span/text()')
    # TIs = [parse_int(x) for x in TIs]

    # stock = {
    #     'code': code,
    #     'ROEs': ROEs,
    #     'last_year_index': last_year_index,
    #     'PBRs': PBRs,
    #     'EPSs': EPSs,
    #     'TAs': TAs,
    #     'NPs': NPs,
    #     'CFOs': CFOs,
    #     'CFIs': CFIs,
    #     'CFFs': CFFs,
    #     'FCFs': FCFs,
    #     'PERs': PERs,
    #     'TIs': TIs,
    #     'DEPTs': DEPTs,
    #     'BPSs': BPSs,
    #     'CAPEXs': CAPEXs,
    # }
    # stock = db.save_stock(stock)

    #parse_quarterly(code)
    #parse_json(code)


def parse_json(code: str):
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
    
    url = NAVER_JSON5 % (code)
    urlopen = urllib.request.urlopen(url)
    data = json.loads(urlopen.read().decode())
    
    CPSs = []
    PCRs = []
    SPSs = []
    PSRs = []
    if data and 'DATA' in data and data['DATA']:
        yyyy = [int(y[:4]) for y in data['YYMM'] if len(y) > 4 and len(y.split('/')) > 2]
        year_data_keys = {y: i+1 for i, y in enumerate(yyyy)}
    
        for row in data['DATA']:
            if 'ACC_NM' in row and row['ACC_NM'].startswith('CPS'):
                CPSs = [(y, row['DATA' + str(year_data_keys[y])]) for y in sorted(list(year_data_keys.keys()))]
            elif 'ACC_NM' in row and row['ACC_NM'].startswith('PCR'):
                PCRs = [(y, row['DATA' + str(year_data_keys[y])]) for y in sorted(list(year_data_keys.keys()))]
            elif 'ACC_NM' in row and row['ACC_NM'].startswith('SPS'):
                SPSs = [(y, row['DATA' + str(year_data_keys[y])]) for y in sorted(list(year_data_keys.keys()))]
            elif 'ACC_NM' in row and row['ACC_NM'].startswith('PSR'):
                PSRs = [(y, row['DATA' + str(year_data_keys[y])]) for y in sorted(list(year_data_keys.keys()))]
                
    
    stock = {
        'code': code,
        'GPs': GPs,
        'CPSs': CPSs,
        'PCRs': PCRs,
        'SPSs': SPSs,
        'PSRs': PSRs,
    }
    print('GPs: {}'.format(GPs))
    stock = db.save_stock(stock)


def parse_etf(code: str, tag: str, etf_type: str):
    url = NAVER + code
    print(url)
    tree = tree_from_url(url, 'euc-kr')

    try:
        title = tree.xpath('//*[@id="middle"]/div[1]/div[1]/h2/a')[0].text
    except:
        return
    month1 = parse_float(tree.xpath('//*[@id="tab_con1"]/div[5]/table/tbody/tr[1]/td/em')[0].text.strip())
    month3 = parse_float(tree.xpath('//*[@id="tab_con1"]/div[5]/table/tbody/tr[2]/td/em')[0].text.strip())
    month6 = parse_float(tree.xpath('//*[@id="tab_con1"]/div[5]/table/tbody/tr[3]/td/em')[0].text.strip())
    month12 = parse_float(tree.xpath('//*[@id="tab_con1"]/div[5]/table/tbody/tr[4]/td/em')[0].text.strip())
    company = tree.xpath('//table[contains(@class, "tbl_type1")]//td/span/text()')[2]

    cost = parse_float(tree.xpath('//table[contains(@class, "tbl_type1")]//td/em/text()')[0])

    tags = tag.split(',')

    db.save_etf({
        'code': code,
        'title': title,
        'company': company,
        'month1': month1,
        'month3': month3,
        'month6': month6,
        'month12': month12,
        'cost': cost,
        'tags': tags,
        'type': etf_type,
    })


def parse_etfs():
    with codecs.open('dual_etf.txt', 'r', 'utf-8') as f:
        lines = f.readlines()
        for line in lines:
            parse_line(line, 'domestic')
    with codecs.open('international_etf.txt', 'r', 'utf-8') as f:
        lines = f.readlines()
        for line in lines:
            parse_line(line, 'international')


def parse_line(line: str, etf_type: str):
    line = line.strip()
    if not line:
        return
    words = line.split(' ')
    parse_etf(words[-1], words[0], etf_type)


def parse_fnguide(code: str):
    print('종목 {} FnGuide...'.format(code))
    url = FNGUIDE + code
    print('FnGuide {}'.format(url))
    tree = tree_from_url(url)
    
    title = first_or_none(tree.xpath('//*[@id="giName"]/text()'))
    if not title:
        return False
    
    groups = first_or_none(tree.xpath('//*[@id="compBody"]/div[1]/div[1]/p/span[1]/text()'))
    groups = groups.split(' ')
    group = groups[1] if len(groups) > 1 else None
    
    subgroup = first_or_none(tree.xpath('//*[@id="compBody"]/div[1]/div[1]/p/span[4]/text()'))
    subgroup = subgroup.replace('\xa0', '')

    closing_month = first_or_none(tree.xpath('//*[@id="compBody"]/div[1]/div[1]/p/span[6]/text()'))
    closing_month = parse_int(closing_month.split(' ')[0][:-1])

    forward_per = parse_float(first_or_none(tree.xpath('//*[@id="corp_group2"]/dl[2]/dd/text()')))
    group_per = parse_float(first_or_none(tree.xpath('//*[@id="corp_group2"]/dl[3]/dd/text()')))
    
    dividend_rate = parse_float(first_or_none(tree.xpath('//*[@id="corp_group2"]/dl[5]/dd/text()')))
    
    relative_earning_rate = parse_float(first_or_none(tree.xpath('//*[@id="svdMainChartTxt13"]/text()')))
    
    momentums = tree.xpath('//*[@id="svdMainGrid1"]/table/tbody/tr[3]/td[1]/span/text()')
    momentums = [parse_float(m) for m in momentums]

    month1 = momentums[0] if len(momentums) >= 1 else 0
    month3 = momentums[1] if len(momentums) >= 2 else 0
    month6 = momentums[2] if len(momentums) >= 3 else 0
    month12 = momentums[3] if len(momentums) >= 4 else 0
    
    foreigner_weight = parse_float(first_or_none(tree.xpath('//*[@id="svdMainGrid1"]/table/tbody/tr[3]/td[2]/text()')))

    beta = parse_float(first_or_none(tree.xpath('//*[@id="svdMainGrid1"]/table/tbody/tr[4]/td[2]/text()')))

    stocks = first_or_none(tree.xpath('//*[@id="svdMainGrid1"]/table/tbody/tr[7]/td[1]/text()'))

    stocks = stocks.split('/ ')
    has_preferred_stock = False if stocks[1] == '0' else True
    
    floating_rate = parse_float(first_or_none(tree.xpath('//*[@id="svdMainGrid1"]/table/tbody/tr[6]/td[2]/text()')))

    YoY = parse_float(first_or_none(tree.xpath('//*[@id="svdMainGrid2"]/table/tbody/tr/td[4]/span/text()')))

    consensus_point = parse_float(first_or_none(tree.xpath('//*[@id="svdMainGrid9"]/table/tbody/tr/td[1]/text()')))
    consensus_price = parse_int(first_or_none(tree.xpath('//*[@id="svdMainGrid9"]/table/tbody/tr/td[2]/text()')))
    consensus_count = parse_int(first_or_none(tree.xpath('//*[@id="svdMainGrid9"]/table/tbody/tr/td[5]/text()')))

    bps = parse_int(first_or_none(tree.xpath('//*[@id="highlight_D_A"]/table/tbody/tr[19]/td[3]/text()')))

    try:
        years = tree.xpath('//*[@id="highlight_D_Y"]/table/thead/tr[2]/th/div/text()')
        years = [x.split('/')[0] for x in years]
        last_year_index = years.index(LAST_YEAR)
    except ValueError:
        print("** 작년 데이터 없음 **")
        return

    NPs = tree.xpath('//*[@id="highlight_D_Y"]/table/tbody/tr[3]/td/text()')
    NPs = [parse_float(x) for x in NPs]

    TAs = tree.xpath('//*[@id="highlight_D_Y"]/table/tbody/tr[6]/td/text()')
    TAs = [parse_float(x) for x in TAs]

    ROEs = tree.xpath('//*[@id="highlight_D_Y"]/table/tbody/tr[17]/td/text()')
    ROEs = [parse_float(x) for x in ROEs]

    EPSs = tree.xpath('//*[@id="highlight_D_Y"]/table/tbody/tr[18]/td/text()')
    EPSs = [parse_float(x) for x in EPSs]

    BPSs = tree.xpath('//*[@id="highlight_D_Y"]/table/tbody/tr[19]/td/text()')
    BPSs = [parse_float(x) for x in BPSs]

    DPSs = tree.xpath('//*[@id="highlight_D_Y"]/table/tbody/tr[20]/td/text()')
    DPSs = [parse_float(x) for x in DPSs]

    PERs = tree.xpath('//*[@id="highlight_D_Y"]/table/tbody/tr[21]/td/text()')
    PERs = [parse_float(x) for x in PERs]

    PBRs = tree.xpath('//*[@id="highlight_D_Y"]/table/tbody/tr[22]/td/text()')
    PBRs = [parse_float(x) for x in PBRs]

    DEPTs = tree.xpath('//*[@id="highlight_D_Y"]/table/tbody/tr[7]/td/text()')
    DEPTs = [parse_float(x) for x in DEPTs]

    stock = {
        'code': code,
        'group': group,
        'subgroup': subgroup,
        'closing_month': closing_month,
        'forward_per': forward_per,
        'group_per': group_per,
        'dividend_rate': dividend_rate,
        'relative_earning_rate': relative_earning_rate,
        'month1': month1,
        'month3': month3,
        'month6': month6,
        'month12': month12,
        'foreigner_weight': foreigner_weight,
        'beta': beta,
        'has_preferred_stock': has_preferred_stock,
        'floating_rate': floating_rate,
        'YoY': YoY,
        'consensus_point': consensus_point,
        'consensus_price': consensus_price,
        'consensus_count': consensus_count,
        'bps': bps,
        'use_fnguide': True,
        'last_year_index': last_year_index,
        'NPs': NPs,
        'TAs': TAs,
        'ROEs': ROEs,
        'EPSs': EPSs,
        'BPSs': BPSs,
        'DPSs': DPSs,
        'PERs': PERs,
        'PBRs': PBRs,
        'DEPTs': DEPTs,
    }
    db.save_stock(stock)
    return True


def row_values_table(table, row_headers: List[str], key: str) -> List[str]:
    try:
        i = row_headers.index(key)
        return [parse_float(v) for v in table.xpath('tbody/tr')[i].xpath('td//text()')]
    except ValueError:
        return []

def row_values_table_by_index(table, index: int) -> List[str]:
    try:
        return [parse_float(v) for v in table.xpath('tbody/tr')[index].xpath('td//text()')]
    except ValueError:
        return []
    except IndexError:
        return []

def parse_fnguide_financial_table(tree) -> dict:
    if not tree.xpath('//*[@id="divDaechaY"]'):
        return {}
    years = tree.xpath('//*[@id="divDaechaY"]/table/thead/tr/th/text()')
    years = [int(y.split('/')[0]) for y in years[1:]]

    row_headers = tree.xpath("//*[@id='divDaechaY']/table/tbody/tr/th//text()")
    row_headers = [h.strip() for h in row_headers if h.strip()]
    row_headers = [h.replace('\xa0', '') for h in row_headers if h != '계산에 참여한 계정 펼치기']

    row_values = partial(row_values_table, tree.xpath("//*[@id='divDaechaY']/table")[0], row_headers)
    current_assets = row_values('유동자산')
    current_liability = row_values('유동부채')
    total_liability = row_values('부채')

    print(years)
    print(current_assets)
    print(current_liability)
    print(total_liability)

    if len(years) != len(current_assets):
        return {}

    current_assets = list(zip(years, current_assets))
    current_liability = list(zip(years, current_liability))
    total_liability = list(zip(years, total_liability))

    return {
        'current_assets': current_assets,
        'current_liability': current_liability,
        'total_liability': total_liability,
    }


def parse_fnguide_profit_table(tree) -> dict:
    if not tree.xpath('//*[@id="divSonikY"]'):
        return {}
    years = tree.xpath('//*[@id="divSonikY"]/table/thead/tr/th/text()')
    years = [int(y.split('/')[0]) for y in years if len(y.split('/')) > 1]

    row_headers = tree.xpath("//*[@id='divSonikY']/table/tbody/tr/th//text()")
    row_headers = [h.strip() for h in row_headers if h.strip()]
    row_headers = [h.replace('\xa0', '') for h in row_headers if h != '계산에 참여한 계정 펼치기']

    row_values = partial(row_values_table, tree.xpath("//*[@id='divSonikY']/table")[0], row_headers)
    sales = row_values('매출액')[:len(years)]
    GPs = row_values('매출총이익')[:len(years)]
    GPs = list(zip(years, GPs))
    sales_cost = row_values('매출원가')[:len(years)]
    SGAs = row_values('판매비와관리비')[:len(years)]

    sales = list(zip(years, sales))
    sales_cost = list(zip(years, sales_cost))
    SGAs = list(zip(years, SGAs))

    print(sales)
    print(sales_cost)
    print(SGAs)
    
    return {
        'sales': sales,
        'sales_cost': sales_cost,
        'SGAs': SGAs,
        'GPs': GPs,
    }

def parse_fnguide_profit_flow(tree) -> dict:
    if not tree.xpath('//*[@id="divCashY"]'):
        return {}
    years = tree.xpath('//*[@id="divCashY"]/table/thead/tr/th/text()')
    years = [int(y.split('/')[0]) for y in years if len(y.split('/')) > 1]

    row_headers = tree.xpath("//*[@id='divCashY']/table/tbody/tr/th//text()")
    row_headers = [h.strip() for h in row_headers if h.strip()]
    row_headers = [h.replace('\xa0', '') for h in row_headers if h != '계산에 참여한 계정 펼치기']

    row_values = partial(row_values_table, tree.xpath("//*[@id='divCashY']/table")[0], row_headers)
    CFOs = list(zip(years, row_values('영업활동으로인한현금흐름')[:len(years)]))
    CFIs = list(zip(years, row_values('투자활동으로인한현금흐름')[:len(years)]))
    CFFs = list(zip(years, row_values('재무활동으로인한현금흐름')[:len(years)]))

    return {
        'CFOs': CFOs,
        'CFIs': CFIs,
        'CFFs': CFFs,
    }

def parse_fnguide_financial_statements(code: str) -> bool:
    print('종목 {} FnGuide 재무재표 ...'.format(code))
    url = FNGUIDE_FINANCIAL_STMT % (code)
    print('FnGuide 재무재표 {}'.format(url))
    tree = tree_from_url(url)
    
    stock = {'code': code, **parse_fnguide_financial_table(tree), **parse_fnguide_profit_table(tree), **parse_fnguide_profit_flow(tree)}
    db.save_stock(stock)
    
    return True


def parse_fnguide_financial_ratio(code: str) -> bool:
    print('종목 {} FnGuide 재무비율 ...'.format(code))
    url = FNGUIDE_FINANCIAL_RATIO % (code)
    print('FnGuide 재무비율 {}'.format(url))
    tree = tree_from_url(url)

    if not tree.xpath('//*[@id="compBody"]/div[2]/div[3]/div[2]/table'):
        return False
    
    years = tree.xpath('//*[@id="compBody"]/div[2]/div[3]/div[2]/table/thead/tr/th/text()')
    years = [int(y.split('/')[0]) for y in years if len(y.split('/')) > 1]

    header1 = '//*[@id="compBody"]/div[2]/div[3]/div[2]/table/tbody/tr/th/text()'
    header2 = '//*[@id="compBody"]/div[2]/div[3]/div[2]/table/tbody/tr/th//a//text()' 
    header3 = '//*[@id="compBody"]/div[2]/div[3]/div[2]/table/tbody/tr/th/div/text()'
    row_headers = tree.xpath(' | '.join([header1, header2, header3]))
    row_headers = [h.strip() for h in row_headers if h.strip()]
    row_headers = [h.replace('\xa0', '') for h in row_headers if h != '계산에 참여한 계정 펼치기']

    row_values = partial(row_values_table, tree.xpath('//*[@id="compBody"]/div[2]/div[3]/div[2]/table')[0], row_headers)
    loan_rate =  list(zip(years, row_values('순차입금비율')[:len(years)]))
    net_current_loan =  list(zip(years, row_values('순차입부채')[:len(years)]))
    interest_cost = list(zip(years, row_values('이자비용')[:len(years)]))
    interest_coverage = list(zip(years, row_values('이자보상배율')[:len(years)]))
    ROICs = list(zip(years, row_values('ROIC')[:len(years)]))
    NOPATs = list(zip(years, row_values('세후영업이익')[:len(years)]))
    ICs = list(zip(years, row_values('영업투하자본')[:len(years)]))

    total_asset_turnover = list(zip(years, row_values('총자산회전율')[:len(years)]))
    net_working_capital_turnover = list(zip(years, row_values('순운전자본회전율')[:len(years)]))
    net_working_capital = list(zip(years, row_values('순운전자본')[:len(years)]))

    stock = {
        'code': code,
        'loan_rate': loan_rate,
        'net_current_loan': net_current_loan,
        'interest_cost': interest_cost,
        'interest_coverage': interest_coverage,
        'ROICs': ROICs,
        'NOPATs': NOPATs,
        'ICs': ICs,
        'total_asset_turnover': total_asset_turnover,
        'net_working_capital_turnover': net_working_capital_turnover,
        'net_working_capital': net_working_capital,
    }
    db.save_stock(stock)

    return True

def parse_fnguide_invest_guide(code: str) -> bool:
    print('종목 {} FnGuide 투자지표 ...'.format(code))
    url = FNGUIDE_INVEST_GUIDE % (code)
    print('FnGuide 투자지표 {}'.format(url))
    tree = tree_from_url(url)

    if not tree.xpath('//*[@id="compBody"]/div[2]/div[5]/div[2]/table'):
        return False

    years = tree.xpath('//*[@id="compBody"]/div[2]/div[5]/div[2]/table/thead/tr/th/text()')
    years = [int(y.split('/')[0]) for y in years if len(y.split('/')) > 1]

    row_values = partial(row_values_table_by_index, tree.xpath('//*[@id="compBody"]/div[2]/div[5]/div[2]/table')[0])
    FCFs = list(zip(years, row_values(50)))
    
    stock = {
        'code': code,
        'FCFs': FCFs,
    }
    db.save_stock(stock)

    return True