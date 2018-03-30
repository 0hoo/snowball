from flask import Flask, request, render_template, redirect, url_for

import db
from scrapper import parse_snowball

app = Flask(__name__)

@app.route('/stocks')
@app.route('/stocks/<status>')
@app.route('/')
def stocks(status=None):
    find = None
    if status == 'starred':
        find = {'starred': True}
    elif status == 'owned':
        find = {'owned': True}
    elif status == 'starredorowned':
        find = {'$or': [{'starred': True}, {'owned': True}]}
    elif status == 'doubtful':
        find = {'doubtful': True}
    elif status == 'roe_max_diff_20':
        find = {'roe_max_diff': {'$lt': 20}, 'roe_count': {'$gte': 4}}
    elif status == 'roe_max_diff_10':
        find = {'roe_max_diff': {'$lt': 10}, 'roe_count': {'$gte': 4}}
    elif status == 'roe_max_diff_5':
        find = {'roe_max_diff': {'$lt': 5}, 'roe_count': {'$gte': 4}}
    order_by = request.args.get('order_by', 'expected_rate')
    ordering = request.args.get('ordering', 'desc')
    stocks = db.all_stocks(order_by=order_by, ordering=ordering, find=find)
    return render_template('stocks.html', stocks=stocks, order_by=order_by, ordering=ordering, status=status)


@app.route('/stocks/fill')
def stocks_fill_snowball_stats():
    [s.fill_snowball_stat() for s in db.all_stocks()]
    return redirect(url_for('stocks'))


@app.route('/stock/<code>')
def stock(code):
    stock = db.stock_by_code(code)
    return render_template('stock_detail.html', stock=stock)


@app.route('/stock/refresh/<code>')
def stock_refresh(code):
    parse_snowball(code)
    return redirect(url_for('stock', code=code))


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


@app.route('/stock/<code>/node', methods=['POST'])
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
    db.save_stock(stock)
    return redirect(url_for('stock', code=code))


@app.route('/stocks/add', methods=['POST'])
def add_stock():
    if request.method == 'POST':
        code = request.form.get('code', None)
        if code:
            parse_snowball(code)
    return redirect('stocks')


if __name__ == '__main__':
    app.debug = True
    app.run()