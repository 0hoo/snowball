import time
from datetime import datetime
from statistics import mean

import requests
from lxml import html

import db

DAUM_BASIC = 'http://finance.daum.net/item/main.daum?code='
NAVER_COMPANY = 'http://companyinfo.stock.naver.com/v1/company/c1010001.aspx?cmp_cd='
NAVER_YEARLY = "http://companyinfo.stock.naver.com/v1/company/ajax/cF1001.aspx?cmp_cd=%s&fin_typ=0&freq_typ=Y"
NAVER_YEARLY_JSON = "http://companyinfo.stock.naver.com/v1/company/cF3002.aspx?cmp_cd=%s&frq=0&rpt=0&finGubun=MAIN&frqTyp=0&cn="
LAST_YEAR = str(datetime.now().year - 1)


def parse_snowball_all():
    for stock in db.all_stocks():
        if stock.get('code', None):
            parse_snowball(stock['code'])
            time.sleep(0.3)


def tree_from_url(url):
    return html.fromstring(requests.get(url).content)


def parse_float(str):
    try:
        return float(str.replace(',', '').replace('%', ''))
    except (ValueError, AttributeError):
        return 0


def parse_int(str):
    try:
        return int(str.replace(',', ''))
    except (ValueError, AttributeError):
        return 0


def parse_basic(code):
    print('종목 {} 기본...'.format(code))
    url = DAUM_BASIC + code
    print('다음 {}'.format(url))
    
    tree = tree_from_url(url)
    if not tree.xpath('//*[@id="topWrap"]/div[1]/h2'):
        return
    
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
    print()


def parse_snowball(code):
    parse_basic(code)
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

    years = list(filter(lambda x: x != '', map(lambda x: x.strip().split('/')[0], tree.xpath('/html/body/table/thead/tr[2]/th/text()'))))
    last_year_index = years.index(LAST_YEAR)

    ROEs = tree.xpath('/html/body/table/tbody/tr[22]/td/span/text()')
    if len(ROEs) == 0:
        print('*** ROE 정보가 없음 >>>')
        return
    
    ROEs = [float(x.replace(',', '')) for x in ROEs]
    is_last_year_roe = True

    if len(ROEs) <= last_year_index:
        is_last_year_roe = False
        print('{last_year}년의 인덱스 {last_year_index}에 대한 ROE 정보가 없음: {ROEs}'.format
          (last_year=LAST_YEAR, last_year_index=last_year_index, ROEs=ROEs))
        last_four_years_roe = ROEs[len(ROEs)-4:len(ROEs)]
    else:
        last_four_years_roe = [ROEs[x] for x in range(last_year_index, last_year_index - 4, -1)]
        last_four_years_roe.reverse()

    EPSs = tree.xpath('/html/body/table/tbody/tr[26]/td/span/text()')
    EPSs = [parse_float(x) for x in EPSs]

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

    PERs = tree.xpath('/html/body/table/tbody/tr[27]/td/span/text()')
    PERs = [parse_float(x) for x in PERs]
    
    #발행주식수
    TIs = tree.xpath('/html/body/table/tbody/tr[33]/td/span/text()')
    TIs = [parse_int(x) for x in TIs]

    stock = {
        'code': code,
        'dividend_rate': dividend_rate,
        'bps': bps,
        'ROEs': ROEs,
        'last_four_years_roe': last_four_years_roe,
        'is_last_year_roe': is_last_year_roe,
        'last_year_index': last_year_index,
        'PBRs': PBRs,
        'EPSs': EPSs,
        'TAs': TAs,
        'NPs': NPs,
        'CFOs': CFOs,
        'PERs': PERs,
        'TIs': TIs,
    }
    stock = db.save_stock(stock)
    stock.fill_snowball_stat()
