from datetime import datetime
from collections import defaultdict

from flask import Flask, request, render_template, redirect, url_for
from bson.objectid import ObjectId

import db
from scrapper import parse_snowball
from utils import mean_or_zero
from etftag import ETFTag

app = Flask(__name__)


VERSION = 1.10
INTEREST = 2.25


@app.route('/stocks')
@app.route('/stocks/<status>')
@app.route('/stocks/<status>/<alt>')
@app.route('/')
def stocks(status=None, alt=None):
    find = None
    stat = {}
    if status == 'starred':
        find = {'starred': True}
    elif status == 'owned':
        find = {'owned': True}
    elif status == 'starredorowned':
        find = {'$or': [{'starred': True}, {'owned': True}]}
    elif status == 'doubtful':
        find = {'doubtful': True}
    order_by = request.args.get('order_by', 'expected_rate')
    ordering = request.args.get('ordering', 'desc')
    filter_id = request.args.get('filter_id', None)

    filters = db.all_filters()
    current_filter = None
    if filter_id:
        current_filter = db.filter_by_id(filter_id)
    
    stocks = db.all_stocks(order_by=order_by, 
        ordering=ordering, find=find, 
        filter_by_expected_rate=find==None, 
        filter_bad=status!='bad', 
        filter_options=(current_filter.filter_options if current_filter else []),
        rank_options=(current_filter.rank_options if current_filter else []))

    if current_filter and current_filter.rank_options:
        order_by = None

    if status in ['owned', 'starred', 'starredorowned']:
        stat['low_pbr'] = len([stock for stock in stocks if stock.pbr <= 1])
        stat['high_expected_rate'] = len([stock for stock in stocks if stock.expected_rate >= 15])
        stat['fscore'] = len([stock for stock in stocks if stock.latest_fscore >= 3])
        stat['mean_expected_rate'] = mean_or_zero([stock.expected_rate for stock in stocks])
        stat['mean_expected_rate_by_low_pbr'] = mean_or_zero([stock.expected_rate_by_low_pbr for stock in stocks])
        stat['mean_future_roe'] = mean_or_zero([stock.future_roe for stock in stocks])
        
        qROE_numbers = [stock.QROEs[0][1] for stock in stocks if len(stock.QROEs) > 0]
        qROE_numbers = [float(roe_number) for roe_number in qROE_numbers if roe_number]
        stat['mean_qROEs'] = mean_or_zero(qROE_numbers)
        stat['qROEs_count'] = len(qROE_numbers)

    return render_template('stocks.html', VERSION=VERSION, stocks=stocks, order_by=order_by, ordering=ordering, status=status,
        available_filter_options=db.available_filter_options, filters=filters,
        current_filter=current_filter, stat=stat, available_rank_options=db.available_rank_options,
        alt=alt)


@app.route('/stocks/filter/new')
def stocks_new_filter():
    filters = db.all_filters()
    name = '새필터' + str(len(filters) + 1)
    filter_id = db.save_filter({
        'name': name,
        'options': [],
    })
    return redirect(url_for('stocks', filter_id=filter_id))


@app.route('/stocks/filter/<filter_id>/save', methods=['POST'])
def stocks_save_filter(filter_id):
    if request.method == 'POST':
        current_filter = db.filter_by_id(filter_id)
        name = request.form.get('filter_name', '')
        current_filter['name'] = name
        db.save_filter(current_filter)
        return redirect(url_for('stocks', filter_id=filter_id))      


@app.route('/stocks/filter/<filter_id>/remove')
def stocks_remove_filter(filter_id):
    db.remove_filter(filter_id)
    return redirect(url_for('stocks'))


@app.route('/stocks/filter/<filter_id>/add_filter_option', methods=['POST'])
def stocks_add_filter_option(filter_id):
    if request.method == 'POST':
        name = request.form.get('filter_name')
        key = request.form.get('filter_option_key')
        morethan = request.form.get('filter_option_morethan')
        morethan = True if morethan == 'morethan' else False
        try:
            value = float(request.form.get('filter_option_value', 0))
        except:
            value = 0
        selected = [filter_option for filter_option in db.available_filter_options if filter_option.key == key][0]
        new_filter_option = db.FilterOption(key, selected.title, morethan, value, selected.is_boolean)
        
        current_filter = db.filter_by_id(filter_id)
        options = current_filter.get('options', [])
        filter_option_dict = new_filter_option._asdict()
        filter_option_dict['_id'] = ObjectId()
        options.append(filter_option_dict)
        current_filter['options'] = options
        current_filter['name'] = name
        db.save_filter(current_filter)

        return redirect(url_for('stocks', filter_id=current_filter['_id']))


@app.route('/stocks/filter/<filter_id>/remove_filter_option/<filter_option_id>')
def stocks_remove_filter_option(filter_id, filter_option_id):
    current_filter = db.filter_by_id(filter_id)
    remain = [o for o in current_filter.get('options', []) if o.get('_id', None) != ObjectId(filter_option_id)]
    current_filter['options'] = remain
    db.save_filter(current_filter)

    return redirect(url_for('stocks', filter_id=current_filter['_id']))


@app.route('/stocks/filter/<filter_id>/add_rank_option')
def stocks_add_rank_option(filter_id):
    rank_option_key = request.args.get('key', None)
    if not rank_option_key:
        return redirect(url_for('stocks', filter_id=filter_id))
    options = [r for r in db.available_rank_options if r.key == rank_option_key]
    if options:
        rank_option_to_add = options[0]
        current_filter = db.filter_by_id(filter_id)
        options = current_filter.get('options', [])
        options.append(rank_option_to_add._asdict())
        db.save_filter(current_filter)

        return redirect(url_for('stocks', filter_id=filter_id, status='rank', alt='alt1'))

    
@app.route('/stocks/filter/<filter_id>/remove_rank_option')
def stocks_remove_rank_option(filter_id):
    rank_option_key = request.args.get('key', None)
    if not rank_option_key:
        return redirect(url_for('stocks', filter_id=filter_id))
    current_filter = db.filter_by_id(filter_id)
    options = current_filter.get('options', [])
    options = [o for o in options if o['key'] != rank_option_key]
    current_filter['options'] = options
    db.save_filter(current_filter)

    return redirect(url_for('stocks', filter_id=filter_id, status='rank', alt='alt1'))


@app.route('/stocks/fill')
def stocks_fill_snowball_stats():
    [s.fill_snowball_stat() for s in db.all_stocks()]
    return redirect(url_for('stocks'))


@app.route('/stock/<code>')
def stock(code):
    stock = db.stock_by_code(code)
    filters = db.all_filters()
    return render_template('stock_detail.html', VERSION=VERSION, stock=stock, filters=filters)


@app.route('/stock/<code>/records')
def stock_records(code):
    import historical
    stock = db.stock_by_code(code)
    records_by_year = historical.records_by_year(stock)
    now = datetime.now()
    records_by_year = [data for data in records_by_year if data[0].year >= now.replace(year=now.year-2).year]
    return render_template('stock_records.html', VERSION=VERSION, stock=stock, records_by_year=records_by_year)


@app.route('/stock/refresh/<code>')
def stock_refresh(code):
    parse_snowball(code)
    return redirect(url_for('stock', code=code))


@app.route('/stock/<code>/expected_rate')
def stock_expected_rate_by_price(code):
    stock = db.stock_by_code(code)
    try:
        expected_rate_price = float(request.args.get('price'))
    except ValueError:
        return redirect(url_for('stock', code=code))
    return render_template('stock_detail.html', VERSION=VERSION, stock=stock, expected_rate_price=expected_rate_price)


@app.route('/stock/<code>/my_price', methods=['POST'])
def stock_my_price(code):
    if request.method == 'POST':
        stock = db.stock_by_code(code)
        stock['my_price'] = float(request.form.get('my_price', 0))
        db.save_stock(stock)
        return redirect(url_for('stock_refresh', code=code))


@app.route('/stock/<code>/adjust', methods=['POST'])
def stock_adjusted_future_roe(code):
    if request.method == 'POST':
        stock = db.stock_by_code(code)
        stock['adjusted_future_roe'] = float(request.form.get('adjusted_future_roe', 0))
        db.save_stock(stock)
        return redirect(url_for('stock_refresh', code=code))


@app.route('/stock/<code>/adjustpbr', methods=['POST'])
def stock_adjusted_future_pbr(code):
    if request.method == 'POST':
        stock = db.stock_by_code(code)
        stock['adjusted_future_pbr'] = float(request.form.get('adjusted_future_pbr', 0))
        db.save_stock(stock)
        return redirect(url_for('stock_refresh', code=code))


@app.route('/stock/<code>/adjustpbr/clear')
def stock_clear_adjusted_future_pbr(code):
    stock = db.stock_by_code(code)
    stock['adjusted_future_pbr'] = 0
    db.save_stock(stock)
    return redirect(url_for('stock_refresh', code=code))


@app.route('/stock/<code>/note', methods=['POST'])
def stock_update_note(code):
    if request.method == 'POST':
        stock = db.stock_by_code(code)
        stock['note'] = str(request.form.get('note', ''))
        db.save_stock(stock)
        return redirect(url_for('stock', code=code))


@app.route('/stock/<code>/clear')
def stock_clear_adjusted_future_roe(code):
    stock = db.stock_by_code(code)
    stock['adjusted_future_roe'] = 0
    db.save_stock(stock)
    return redirect(url_for('stock_refresh', code=code))


@app.route('/stock/<code>/<status>/<on>')
def stock_status(code, status, on):
    stock = db.stock_by_code(code)
    stock[status] = on == 'on'
    if status == 'owned' and stock[status]:
        stock['starred'] = False
    elif status == 'starred' and stock[status]:
        stock['owned'] = False
    db.save_stock(stock)
    return redirect(url_for('stock', code=code))


@app.route('/stocks/add', methods=['POST'])
def add_stock():
    if request.method == 'POST':
        code = request.form.get('code', None)
        if code:
            parse_snowball(code)
    return redirect('stocks')


@app.route('/stocks/<code>/remove')
def remove_stock(code):
    db.remove_stock(code)
    return redirect(url_for('stocks'))


@app.route('/etfs/<etf_type>')
def etfs(etf_type='domestic'):
    momentum_base = 'month3' if etf_type == 'domestic' else 'month6'
    momentum_base_kr = '3개월' if etf_type == 'domestic' else '6개월'
    order_by = request.args.get('order_by', momentum_base)
    ordering = request.args.get('ordering', 'desc')
    etfs = db.all_etf(order_by=order_by, ordering=ordering, etf_type=etf_type)
    bond_etfs = ['148070', '152380']
    tags = defaultdict(list)
    for etf in etfs:
        for tag in etf.get('tags'):
            tags[tag].append(etf)
    tags = {k: ETFTag(k, v) for k, v in tags.items()}
    
    stat = {}
    etfs_by_momentum_base = [etf for etf in db.all_etf(order_by=momentum_base, ordering='desc', etf_type=etf_type) if etf[momentum_base] != 0]
    no_bond_etfs = sorted([etf for etf in etfs_by_momentum_base if etf['code'] not in bond_etfs], key=lambda x: x.get(momentum_base, 0), reverse=True)
    stat['absolute_momentum_momentum_base_avg'] = mean_or_zero([etf[momentum_base] for etf in no_bond_etfs])
    stat['absolute_momentum_high'] = no_bond_etfs[0]
    stat['relative_momentum_etf'] = etfs_by_momentum_base[0]
    
    tags = sorted(tags.values(), key=lambda t: getattr(t, momentum_base), reverse=True)
    
    filters = db.all_filters()
    
    return render_template('etfs.html', VERSION=VERSION, INTEREST=INTEREST, filters=filters, etfs=etfs, order_by=order_by, ordering=ordering, 
        stat=stat, tags=tags, etf_type=etf_type, momentum_base=momentum_base, momentum_base_kr=momentum_base_kr)


if __name__ == '__main__':
    app.debug = True
    app.run()