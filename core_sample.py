import requests
from lxml import html


DAUM_BASIC = 'http://finance.daum.net/item/main.daum?code='
NAVER_COMPANY = 'http://companyinfo.stock.naver.com/v1/company/c1010001.aspx?cmp_cd='
NAVER_YEARLY = "http://companyinfo.stock.naver.com/v1/company/ajax/cF1001.aspx?cmp_cd=%s&fin_typ=0&freq_typ=Y"


def basic(code):
    url = DAUM_BASIC + code
    content = requests.get(url).content
    tree = html.fromstring(content)
    title = tree.xpath('//*[@id="topWrap"]/div[1]/h2')[0].text
    price = tree.xpath('//*[@id="topWrap"]/div[1]/ul[2]/li[1]/em')[0].text
    price = float(price.replace(',', ''))

    return (title, price)


def bps(code):
    url = 'http://companyinfo.stock.naver.com/v1/company/c1010001.aspx?cmp_cd=' + code
    content = requests.get(url).content
    tree = html.fromstring(content)
    
    bps = tree.xpath('//*[@id="pArea"]/div[1]/div/table/tr[3]/td/dl/dt[2]/b')[0].text
    bps = int(bps.replace(',', ''))
    return bps


def snowball(code):
    url = NAVER_YEARLY % code
    content = requests.get(url).content
    tree = html.fromstring(content)
    
    ROEs = tree.xpath('/html/body/table/tbody/tr[22]/td/span/text()')
    ROEs = [float(v.replace(',', '')) for v in ROEs]
    count = len(ROEs)
    return ROEs[:count-3], ROEs[count-3:]


def future_bps(bps, future_roe, future=10):
    return int(bps * ((1 + (1 * future_roe / 100)) ** future))


def expected_rate(future_bps, price, future=10):
    return ((future_bps / price) ** (1.0 / future) - 1) * 100


def invest_price(future_bps, target_rate=15, future=10):
    return int(future_bps / ((1 + (target_rate / 100)) ** future))

