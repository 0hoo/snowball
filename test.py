import unittest
from datetime import datetime
from statistics import mean

from db import Stock, DIVIDEND_TAX_RATE


LAST_YEAR = datetime.now().year - 1


class StockTest(unittest.TestCase):
    def test_dict_to_stock(self):
        stock_dict = {
            'code': '0001',
        }
        self.assertIsNotNone(Stock(stock_dict))
        self.assertEqual(stock_dict['code'], Stock(stock_dict)['code'])

    def test_dividend_tax_adjust(self):
        stock_dict = {
            'code': '0001',
        }
        self.assertEqual(0.0, Stock(stock_dict).dividend_tax_adjust)
        
        dividend_rate = 3.5
        stock_dict['dividend_rate'] = dividend_rate
        stock = Stock(stock_dict)
        self.assertAlmostEqual(0.539, Stock(stock_dict).dividend_tax_adjust)
        self.assertEqual(dividend_rate * (DIVIDEND_TAX_RATE / 100), Stock(stock_dict).dividend_tax_adjust)


class StockYearStatTest(unittest.TestCase):
    def test_roe_year_stat_empty(self):
        stock_dict = {
            'code': '0001',
        }
        empty_year_stat = [(0, 0)]
        self.assertEqual(empty_year_stat, Stock(stock_dict).year_stat('ROEs'))

    def test_roe_year_stat_should_have_last_year_index(self):
        stock_dict = {
            'code': '0001',
            'ROEs': [3.0],
        }
        self.assertRaises(AssertionError, Stock(stock_dict).year_stat, 'ROEs')

        stock_dict['last_year_index'] = 0
        self.assertEqual([(LAST_YEAR, 3.0)], Stock(stock_dict).roes)

        stock_dict['last_year_index'] = 1
        self.assertEqual([(LAST_YEAR - 1, 3.0)], Stock(stock_dict).roes)

    def test_roe_year_stat(self):
        stock_dict = {
            'code': '0001',
            'ROEs': [3.0, 5.0, 4.0, 10.0],
            'last_year_index': 2,
        }
        roes = Stock(stock_dict).year_stat('ROEs')
        self.assertEqual(4, len(roes))
        
        expected_roes = [(LAST_YEAR-2, 3.0), (LAST_YEAR-1, 5.0), (LAST_YEAR, 4.0), (LAST_YEAR+1, 10)]
        self.assertEqual(expected_roes, roes)

    def test_countable_roe(self):
        stock_dict = {
            'code': '0001',
            'ROEs': [3.0, 5.0, None, 10.0],
            'last_year_index': 3,
        }
        stock = Stock(stock_dict)
        self.assertEqual([(2014, 3.0), (2015, 5.0), (2016, None), (2017, 10)], stock.year_stat('ROEs'))
        self.assertEqual([3.0, 5.0, 10.0], stock.countable_roes)
        self.assertEqual(mean([3.0, 5.0, 10.0]), stock.mean_roe)

    def test_last_four_years_roe(self):
        stock_dict = {
            'code': '0001',
            'ROEs': [3.0, 5.0, 4.0, 10.0],
            'last_year_index': 2,
        }
        last_four_years = Stock(stock_dict).last_four_years_roe
        self.assertEqual(3, len(last_four_years))
        self.assertEqual([3.0, 5.0, 4.0], last_four_years)
        
        stock_dict['last_year_index'] = 3
        last_four_years = Stock(stock_dict).last_four_years_roe
        self.assertEqual(4, len(last_four_years))
        self.assertEqual([3.0, 5.0, 4.0, 10.0], last_four_years)
        
        stock_dict['last_year_index'] = 0
        last_four_years = Stock(stock_dict).last_four_years_roe
        self.assertEqual(1, len(last_four_years))
        self.assertEqual([3.0], last_four_years)

    def test_mean_roe(self):
        stock_dict = {
            'code': '0001',
            'ROEs': [3.0, 5.0, 4.0, 10.0],
            'last_year_index': 2,
        }
        self.assertEqual(mean([3.0, 5.0, 4.0]), Stock(stock_dict).mean_roe)

        stock_dict['last_year_index'] = 1
        self.assertEqual(mean([3.0, 5.0]), Stock(stock_dict).mean_roe)

    def test_calculated_roe_count(self):
        stock_dict = {
            'code': '0001',
            'ROEs': [3.0, 5.0, 4.0, 10.0],
            'last_year_index': 2,
        }
        print(Stock(stock_dict).calculated_roe_count)

    def test_future_roe(self):
        stock_dict = {
            'code': '0001',
            'ROEs': [3.0, 5.0, 4.0, 10.0],
            'last_year_index': 2,
        }
        stock = Stock(stock_dict)
        self.assertEqual(0.0, stock.dividend_tax_adjust)
        self.assertEqual(stock.mean_roe, stock.future_roe)

        stock_dict['dividend_rate'] = 4.5
        stock = Stock(stock_dict)
        self.assertAlmostEqual(0.693, stock.dividend_tax_adjust)
        self.assertEqual(stock.mean_roe - stock.dividend_tax_adjust, stock.future_roe)

    def test_calc_future_bps(self):
        stock_dict = {
            'code': '0001',
            'bps': 1000,
            'ROEs': [11.0, 8.0, 15.0, 10.0],
            'last_year_index': 2,
            'dividend_rate': 4.5,
        }
        
        stock = Stock(stock_dict)
        self.assertAlmostEqual(10.64, stock.future_roe, places=1)
        self.assertEqual(int(1000 + 1000 * 0.1064), stock.calc_future_bps(1))
        self.assertEqual(2748, stock.calc_future_bps(10))

        stock['adjusted_future_roe'] = 12.0
        self.assertEqual(1973, stock.calc_future_bps(6))
        self.assertEqual(3105, stock.calc_future_bps(10))

    def test_expected_rate(self):
        stock_dict = {
            'code': '0001',
            'current_price': 1200,
            'bps': 1000,
            'ROEs': [11.0, 8.0, 15.0, 10.0],
            'last_year_index': 2,
            'dividend_rate': 4.5,
        }
        self.assertAlmostEqual(8.63, Stock(stock_dict).expected_rate, places=1)
        stock_dict['current_price'] = 1000
        self.assertAlmostEqual(10.63, Stock(stock_dict).expected_rate, places=1)
        stock_dict['current_price'] = 800
        self.assertAlmostEqual(13.13, Stock(stock_dict).expected_rate, places=1)

    def test_invest_price(self):
        stock_dict = {
            'code': '0001',
            'bps': 1000,
            'ROEs': [11.0, 8.0, 15.0, 10.0],
            'last_year_index': 2,
            'dividend_rate': 4.5,
        }
        self.assertEqual(679, Stock(stock_dict).invest_price)        
        stock_dict['bps'] = 1800
        self.assertEqual(1222, Stock(stock_dict).invest_price)
        stock_dict['ROEs'] = [15.0, 18.0, 20.0, 22.0]        
        self.assertEqual(2133, Stock(stock_dict).invest_price)

    def test_expected_rate_by_current_pbr(self):
        stock_dict = {
            'code': '0001',
            'bps': 1000,
            'ROEs': [11.0, 8.0, 15.0, 10.0],
            'last_year_index': 2,
            'dividend_rate': 4.5,
            'current_price': 1200
        }
        stock = Stock(stock_dict)
        self.assertAlmostEqual(8.63, stock.expected_rate, places=1)

        stock['pbr'] = float(stock['current_price'] / stock['bps'])
        self.assertAlmostEqual(1.2, stock['pbr'], places=1)
        self.assertEqual(int(stock.calc_future_bps(1) * stock['pbr']), stock.calc_future_price_current_pbr(1))
        self.assertEqual(1327, stock.calc_future_price_current_pbr(1))
        self.assertAlmostEqual(10.63, stock.expected_rate_by_current_pbr, places=1)

    def test_expected_rate_by_low_pbr(self):
        stock_dict = {
            'code': '0001',
            'bps': 1000,
            'ROEs': [11.0, 8.0, 15.0, 10.0],
            'last_year_index': 2,
            'dividend_rate': 4.5,
            'current_price': 1200
        }
        stock = Stock(stock_dict)
        stock['PBRs'] = [1.0, 0.8, 0.7, 0.5]
        self.assertEqual(0.7, stock.low_pbr)
        stock['PBRs'] = [0.0, 0.8, 0.7, 0.5]
        self.assertEqual(0.7, stock.low_pbr)
        self.assertEqual(774, stock.calc_future_price_low_pbr(1))
        self.assertAlmostEqual(4.82, stock.expected_rate_by_low_pbr, places=1)
        
    def test_expected_rate_by_mid_pbr(self):
        stock_dict = {
            'code': '0001',
            'bps': 1000,
            'ROEs': [11.0, 8.0, 15.0, 10.0],
            'PBRs': [0.0, 0.8, 0.7, 0.5],
            'last_year_index': 2,
            'dividend_rate': 4.5,
            'current_price': 1200,
            'pbr': 0.9
        }
        stock = Stock(stock_dict)
        self.assertEqual(0.7, stock.low_pbr)
        self.assertEqual((stock['pbr'] + stock.low_pbr) / 2.0, stock.mid_pbr)
        self.assertAlmostEqual(6.23, stock.expected_rate_by_mid_pbr, places=1)

    def test_adjusted_eps(self):
        stock_dict = {
            'code': '0001',
        }
        self.assertEqual(0, Stock(stock_dict).adjusted_eps)
        stock_dict['EPSs'] = [1000, 1500]
        stock_dict['last_year_index'] = 2
        self.assertEqual(0, Stock(stock_dict).adjusted_eps)
        stock_dict['EPSs'] = [1000, 1500, 2000]
        self.assertEqual(1666, Stock(stock_dict).adjusted_eps)
        
    def test_intrinsic_value(self):
        stock_dict = {
            'code': '0001',
            'bps': 1000,
            'EPSs': [100, 150, 200],
            'last_year_index': 2,
        }
        stock = Stock(stock_dict)
        self.assertEqual(int((stock['bps'] + (stock.adjusted_eps * 10)) / 2), stock.intrinsic_value)

    def test_intrinsic_discount_rate(self):
        stock_dict = {
            'code': '0001',
            'bps': 1000,
            'EPSs': [100, 150, 200],
            'last_year_index': 2,
            'current_price': 1200
        }
        self.assertAlmostEqual(10.83, Stock(stock_dict).intrinsic_discount_rate, places=1)

    def test_eps_growth(self):
        stock_dict = {
            'code': '0001',
        }
        self.assertEqual(0, Stock(stock_dict).eps_growth)
        stock_dict['EPSs'] = [100, 150, 200]
        self.assertAlmostEqual(41.66, Stock(stock_dict).eps_growth, places=1)

    def test_peg_current_per(self):
        stock_dict = {
            'code': '0001',
        }
        self.assertEqual(0, Stock(stock_dict).peg_current_per)
        stock_dict['per'] = 6
        self.assertEqual(0, Stock(stock_dict).peg_current_per)
        stock_dict['EPSs'] = [100, 110, 130]
        self.assertAlmostEqual(0.42, Stock(stock_dict).peg_current_per, places=1)
        stock_dict['per'] = 10
        self.assertAlmostEqual(0.70, Stock(stock_dict).peg_current_per, places=1)
        
    def test_peg_mean_per(self):
        stock_dict = {
            'code': '0001',
        }
        stock = Stock(stock_dict)
        self.assertEqual(0, stock.mean_per)

        stock_dict['PERs'] = [8, 5.5, 11.5]
        stock = Stock(stock_dict)
        self.assertAlmostEqual(8.33, stock.mean_per, places=1)
        
        stock_dict['EPSs'] = [100, 110, 130]
        stock = Stock(stock_dict)
        self.assertAlmostEqual(0.59, stock.peg_mean_per, places=1)        

    def test_fscore(self):
        pass

    def test_roe_max_diff(self):
        stock_dict = {
            'code': '0001',
        }
        stock = Stock(stock_dict)
        self.assertEqual(0, stock.roe_max_diff)
        stock_dict['ROEs'] = [10, 5, 11]
        stock = Stock(stock_dict)
        self.assertEqual(6, stock.roe_max_diff)


if __name__ == '__main__':
    unittest.main()