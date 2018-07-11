import argparse

import scrapper

parser = argparse.ArgumentParser(description='Snowball utility')
parser.add_argument('--basic', help='입력된 종목코드의 기본 정보를 가지고 온다')
parser.add_argument('--snowball', help='입력된 종목코드의 스노우볼 정보를 가지고 온다')
parser.add_argument('--mysnowball', action='store_true', help='관심종목과 소유종목의 스노우볼 정보를 가지고 온다')
parser.add_argument('--allsnowball', action='store_true', help='모든 기대수익률이 0이상인 종목의 스노우볼 정보를 가지고 온다')
parser.add_argument('--allminus', action='store_true', help='기대수익률이 0이하인 종목의 스노우볼 정보를 가지고 온다')
parser.add_argument('--fill', action='store_true', help='company.csv 파일에 있는 종목을 전부 추가한다')
parser.add_argument('--sample', action='store_true', help='sample.csv 파일에 있는 종목을 추가한다')
parser.add_argument('--etf', action='store_true', help='ETF 듀얼 모멘텀 정보를 수집한다')

if __name__ == '__main__':
    args = parser.parse_args()
    if args.basic:
        scrapper.parse_basic(args.basic)
    elif args.snowball:
        scrapper.parse_snowball(args.snowball)
    elif args.mysnowball:
        scrapper.parse_snowball_stocks(filter_bad=True, only_starred_owned=True)
    elif args.allsnowball:
        scrapper.parse_snowball_stocks(filter_bad=True)
    elif args.allminus:
        scrapper.parse_snowball_stocks(filter_bad=False)
    elif args.fill:
        scrapper.fill_company()
    elif args.sample:
        scrapper.fill_company(filename='sample.csv')
    elif args.etf:
        scrapper.parse_etfs()
