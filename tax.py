import datetime
import requests
import sqlite3
import sys
import re
from math import ceil
from sqlite3 import Error

# constants
db_filename = 'db'
rate_api = 'https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date={}&json'


# api example:
# [{"r030":36,"txt":"...","rate":17.18555,"cc":"AUD","exchangedate":"28.10.2019"},...


# classes
class Income:
    def __init__(self, _id, date, currency, amount, tax, rate):
        self.id = _id
        self.date = date
        self.currency = currency
        self.amount = amount
        self.tax = tax
        self.rate = rate


# functions
def to_int(s):
    try:
        return int(s)
    except ValueError:
        return 0


def to_float(s):
    try:
        return float(s)
    except ValueError:
        return .0


def fetch_rate(date, currency):
    url = rate_api.format(date)
    r = requests.get(url)
    if r.status_code != 200:
        return 0
    data = r.json()
    for d in data:
        if d["cc"] == currency:
            return to_float(d["rate"])
    return .0


def reformat_date(date, old_format, new_format):
    d = datetime.datetime.strptime(date, old_format)
    return d.strftime(new_format)


def date_quarter(date, _format):
    d = datetime.datetime.strptime(date, _format)
    return 'Q{}'.format(int((d.month-1) / 3.) + 1)


def round_up(num):
    return ceil(num * 100) / 100.0


# sqlite
def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print 'sqlite3', sqlite3.version
    except Error as e:
        print(e)
    return conn


def create_table(conn, create_table_sql):
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e)


def create_income(conn, income):
    sql = ''' INSERT INTO income(date, currency, amount, tax, rate)
              VALUES(?,?,?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, income)
    conn.commit()
    return cur.lastrowid


def delete_income(conn, _id):
    cur = conn.cursor()
    cur.execute(''' DELETE FROM income WHERE id=? ''', (_id,))
    conn.commit()


def select_income_by_id(conn, _id):
    cur = conn.cursor()
    cur.execute("SELECT id, date, currency, amount, tax, rate FROM income WHERE id=?", (_id,))
    rows = cur.fetchall()
    if rows:
        return Income(*rows[0])
    return None


def select_all_incomes(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, date, currency, amount, tax, rate FROM income ORDER BY date DESC")
    rows = cur.fetchall()
    incomes = []
    for row in rows:
        incomes.append(Income(*row))
    return incomes


def connect(db_file):
    conn = create_connection(db_file)
    if conn is not None:
        create_table(conn, """ CREATE TABLE IF NOT EXISTS income (
                                    id integer PRIMARY KEY,
                                    date text NOT NULL,
                                    currency text NOT NULL,
                                    amount real NOT NULL,
                                    tax real NOT NULL,
                                    rate real NOT NULL
                                ); """)
    else:
        print("Error! cannot create the database connection.")
        sys.exit()
    return conn


# commands
def do_remove(conn, _id):
    if _id == 0:
        print("Error! invalid args.")
        return

    inc = select_income_by_id(conn, _id)
    if inc:
        delete_income(conn, inc.id)
        print('removed #{}: {} {} {} {} {}'.format(inc.id, inc.date, inc.currency, inc.amount, inc.tax, inc.rate))
    else:
        print("Error! Found no such id.")


def do_add(conn, date, curr, amount, tax):
    try:
        datetime.datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        print("Error! date should be YYYY-MM-DD.")
        return

    if re.compile("^[A-Z][A-Z][A-Z]$").match(curr) is False:
        print("Error! currency should be XYZ.")
        return

    if amount == .0 or tax == .0:
        print("Error! invalid args.")
        return

    rate = 1.
    if curr != "UAH":
        date_for_api = reformat_date(date, '%Y-%m-%d', '%Y%m%d')
        rate = fetch_rate(date_for_api, curr)
        if rate == .0:
            print('Error! No rate for date {}.'.format(date_for_api))
            return

    inc = Income(0, date, curr, amount, tax, rate)
    _id = create_income(conn, (inc.date, inc.currency, inc.amount, inc.tax, inc.rate))
    print('added #{}'.format(_id))


def do_print(conn):
    incomes = select_all_incomes(conn)
    # order by date desc

    for i in sorted(incomes, key=lambda inc: inc.id):
        print('{:>6}: {} {} amount: {:>12} tax: {:>6}'.format(i.id, i.date, i.currency, i.amount, i.tax))

    print('{:>15}'.format('-' * 10))

    periods = {}

    for i in incomes:
        val = round_up(i.amount * i.rate)
        tax = val * i.tax

        _m = reformat_date(i.date, '%Y-%m-%d', '%Y-%m')
        _q = reformat_date(i.date, '%Y-%m-%d', '%Y') + ' ' + date_quarter(i.date, '%Y-%m-%d')
        _y = reformat_date(i.date, '%Y-%m-%d', '%Y')

        if _m not in periods:
            periods[_m] = [.0, .0]
        if _q not in periods:
            periods[_q] = [.0, .0]
        if _y not in periods:
            periods[_y] = [.0, .0]

        periods[_m][0] = periods[_m][0] + val
        periods[_m][1] = periods[_m][1] + tax
        periods[_q][0] = periods[_q][0] + val
        periods[_q][1] = periods[_q][1] + tax
        periods[_y][0] = periods[_y][0] + val
        periods[_y][1] = periods[_y][1] + tax

    for k, v in sorted(periods.items()):
        print('{:>12}: sum: {:>12} tax: {:>12}'.format(k, v[0], round_up(v[1])))


# args
print 'Usage: python tax.py <command> [<args>]'

argc = len(sys.argv)
if argc <= 1:
    sys.exit()

cmd = sys.argv[1]
if cmd == 'add' and argc == 6:
    do_add(connect(db_filename), sys.argv[2], sys.argv[3], to_float(sys.argv[4]), to_float(sys.argv[5]))
elif cmd == 'remove' and argc == 3:
    do_remove(connect(db_filename), to_int(sys.argv[2]))
elif cmd == 'print' and argc == 2:
    do_print(connect(db_filename))
else:
    print('Error! invalid command.')
