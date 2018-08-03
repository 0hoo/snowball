from utils import mean_or_zero


class ETFTag:
    def __init__(self, tag, etfs=[]):
        self.tag = tag
        self.etfs = sorted(etfs, key=lambda e: e.get('month3', 0), reverse=True)

    @property
    def month1(self):
        return mean_or_zero([etf['month1'] for etf in self.etfs])

    @property
    def month3(self):
        return mean_or_zero([etf['month3'] for etf in self.etfs])
    
    @property
    def month6(self):
        return mean_or_zero([etf['month6'] for etf in self.etfs])

    @property
    def month12(self):
        return mean_or_zero([etf['month12'] for etf in self.etfs])