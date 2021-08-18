"""Evaluation library."""

__copyright__ = "Copyright (C) 2021  Martin Blais"
__license__ = "GNU GPLv2"

from decimal import Decimal
from os import path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union, NamedTuple
import argparse
import collections
import copy
import csv
import datetime
import io
import logging
import math
import os
import re
import time
import urllib.parse

from dateutil import parser
from more_itertools import first
import ameritrade
import click
import jinja2

from johnny.base.etl import petl, Table, Record
from overnight import earnings_pb2 as pb


Json = Union[Dict[str, 'Json'], List['Json'], str, int, float]
ZERO = Decimal('0')
Q = Decimal('0.01')


# Data for each strike in a chain.
StrikeData = dict[str, Any]


class Expi(NamedTuple):
    """Data for one expiration."""
    info: dict[str, Any]
    puts: list[StrikeData]
    calls: list[StrikeData]


class Chain(NamedTuple):
    """Normalized data for an options chain."""
    info: dict[str, Any]
    expis: dict[datetime.date, Expi]


def normalize_chain(chain_json: Json) -> Chain:
    """Normalize a TD chain response to a simple structure, joining puts and calls
    by expiration."""
    assert chain_json['callExpDateMap'].keys() == chain_json['putExpDateMap'].keys()
    expis = {}
    for expi_str in chain_json['callExpDateMap']:
        expiration = parser.parse(expi_str.split(':')[0]).date()

        puts_json = chain_json['putExpDateMap'][expi_str]
        calls_json = chain_json['callExpDateMap'][expi_str]
        puts = sorted([datalist[0] for datalist in puts_json.values()],
                      key=lambda r: r['strikePrice'], reverse=True)
        calls = sorted([datalist[0] for datalist in calls_json.values()],
                       key=lambda r: r['strikePrice'])

        any_option = first(calls_json.values())[0]
        info = {attr: any_option[attr]
                for attr in ['daysToExpiration', 'expirationDate', 'expirationType']}
        info['expiration'] = expiration

        expis[expiration] = Expi(info, puts, calls)

    chain_info = chain_json.copy()
    del chain_info['callExpDateMap']
    del chain_info['putExpDateMap']
    return Chain(chain_info, expis)


def is_regular_expiration(expi: Expi) -> bool:
    """Return true if this is a regular expiration."""
    return expi.info['expirationType'] == 'R'


def find_regular_expirations(chain: Chain) -> Iterator[Expi]:
    """Return the first regular expiration."""
    for date, expi in sorted(chain.expis.items()):
        if is_regular_expiration(expi):
            yield expi


def get_closest_strike(strikes: list[StrikeData],
                       target_price: Decimal) -> tuple[Decimal, int]:
    """Return the closest strike and index from the list."""
    _, strikePrice, index = min([
        (abs(strike.strikePrice - target_price), strike.strikePrice, index)
        for index, strike in enumerate(strikes)])
    return strikePrice.quantize(Q), index


def index_with_default(alist: list[Any], index: int, default: Any) -> Any:
    """Index into a list with a default value."""
    try:
        return alist[index]
    except IndexError:
        return default


def estimate_expected_move(chain_info, expi: Expi) -> Optional[tuple[Decimal, Decimal]]:
    """Compute estimates of the expected move."""

    # Get the closest strikes for a series of concentric straddles.
    underlyingPrice = chain_info['underlying']['mark']
    try:
        putStrikePrice, index = get_closest_strike(expi.puts, underlyingPrice)
        put0 = expi.puts[index]
        put1 = index_with_default(expi.puts, index + 1, None)
        put2 = index_with_default(expi.puts, index + 2, None)

        callStrikePrice, index = get_closest_strike(expi.calls, underlyingPrice)
        call0 = expi.calls[index]
        call1 = index_with_default(expi.calls, index + 1, None)
        call2 = index_with_default(expi.calls, index + 2, None)
    except IndexError:
        return

    # TODO(blais): Check averaging the square.
    if call0['volatility'] == 'NaN' or put0['volatility'] == 'NaN':
        return
    atm_volatility = (call0['volatility'] + put0['volatility'])/2 / 100

    em_implied = Decimal(float(atm_volatility) *
                         math.sqrt(expi.info['daysToExpiration'] / 365) *
                         float(underlyingPrice)).quantize(Q)

    # Estimate using 60% of 1 strike strangle + 30% of 2 strike strangle + 10%
    # of 3 strike strangle.
    em_straddles = (Decimal('0.60') * (put0.mark + call0.mark) +
                    Decimal('0.30') * (put1.mark if put1 else ZERO +
                                       call1.mark if call1 else ZERO) +
                    Decimal('0.10') * (put2.mark if put2 else ZERO +
                                       call2.mark if call2 else ZERO)).quantize(Q)

    return em_straddles, em_implied, atm_volatility


def get_company_description(chain: Chain) -> str:
    """Return the company name."""
    return chain.info['underlying']['description']


def get_clean_name(name: str) -> str:
    """Return a cleaned up version of the name, removing common suffixes."""
    return (re.sub(r"(Common Stock|Registered Shares|Inc\.?|S\.A\.|Class [ABC12].*)",
                   "", name)
            .strip(' -,'))


def safe_quantize(value: Decimal, quantum: Decimal) -> Decimal:
    """Quantize the given value, supporting exceptions for NaNs."""
    if value == 'NaN':
        return ZERO
    return value.quantize(quantum)


def get_term(chain: Chain, expi: Expi, config: pb.Config) -> pb.Expiration:
    """Get data for one expiration."""

    # Error messages returned.
    x = pb.Expiration()

    # Store metadata about the term/expiration.
    x.is_regular = is_regular_expiration(expi)
    x.days = expi.info['daysToExpiration']
    expiration = expi.info['expiration']
    x.date.year = expiration.year
    x.date.month = expiration.month
    x.date.day = expiration.day

    # Estimate the expected move a few ways.
    em_data = estimate_expected_move(chain.info, expi)
    if em_data is None:
        x.diagnostics.append("ERROR: Could not calculate EM")
        return x
    em_straddle, em_implied, x.atm_iv = em_data
    em_effective = (em_straddle + em_implied * Decimal('0.85')) / 2
    underlying_price = chain.info['underlying']['mark']
    x.em_straddle = em_straddle
    x.em_implied = em_implied
    x.em_effective = em_effective

    # Calculate targets for strikes.
    width = Decimal(config.strangle_em_width) * em_effective
    x.put.target = put_target_strike = (underlying_price - width).quantize(Q)
    x.call.target = call_target_strike = (underlying_price + width).quantize(Q)

    # Select candidate strikes.
    x.put.strike, index = get_closest_strike(expi.puts, put_target_strike)
    put_strike = expi.puts[index]
    if put_strike['bidSize'] < config.min_size or put_strike['askSize'] < config.min_size:
        x.diagnostics.append(
            f"WARNING: No size on puts ({put_strike['bidSize']} x {put_strike['askSize']})")
    x.call.strike, index = get_closest_strike(expi.calls, call_target_strike)
    call_strike = expi.calls[index]
    if call_strike['bidSize'] < config.min_size or call_strike['askSize'] < config.min_size:
        x.diagnostics.append(f"WARNING: No size on calls "
                             f"({call_strike['bidSize']} x {call_strike['askSize']})")

    # Evaluate the price of the position.
    x.put.mark = put_strike['mark']
    x.call.mark = call_strike['mark']
    x.strangle_cr = x.put.mark + x.call.mark

    # Evaluate suitability of the spreads (on the option value).
    # TODO(blais): Make this more robust by looking at neighboring strikes.
    x.put.spread = put_strike['ask'] - put_strike['bid']
    x.call.spread = call_strike['ask'] - call_strike['bid']
    x.put.spread_frac = x.put.spread / x.put.mark if x.put.mark else 0
    x.call.spread_frac = x.call.spread / x.call.mark if x.call.mark else 0

    # Flag missing greeks.
    if put_strike['delta'] == 'NaN' or call_strike['delta'] == 'NaN':
        x.diagnostics.append("ERROR: Delta is NaN")

    # Flag excessive deltas.
    x.put.delta = safe_quantize(put_strike['delta'], Q)
    x.call.delta = safe_quantize(call_strike['delta'], Q)
    if abs(x.put.delta) > config.max_delta or abs(x.call.delta) > config.max_delta:
        x.diagnostics.append(f"WARNING: Delta is too large (>{config.max_delta})")

    # Check for enough credits.
    if x.strangle_cr < config.min_strangle_credits:
        x.diagnostics.append(
            f"WARNING: Not enough credits received (<{config.min_strangle_credits})")

    # Check relative spread size.
    if x.put.spread_frac > config.max_spread_frac:
        x.diagnostics.append(
            f"WARNING: Put spreads are wide (>{config.max_spread_frac:.0%})")
    if x.call.spread_frac > config.max_spread_frac:
        x.diagnostics.append(
            f"WARNING: Call spreads are wide (>{config.max_spread_frac:.0%})")

    return x


def analyze_earnings(chain_json: Json,
                     config: pb.Config) -> pb.Earnings:
    """Run the analysis on a single earnings name."""

    # Store properties of the chain.
    earnings = pb.Earnings()
    chain = normalize_chain(chain_json)
    earnings.underlying = chain.info['symbol']
    earnings.name = get_company_description(chain)

    # Store basic stats on the stock.
    underlying = chain.info['underlying']
    earnings.price = underlying['mark']
    earnings.year_high = underlying['fiftyTwoWeekHigh']
    earnings.year_low = underlying['fiftyTwoWeekLow']
    earnings.percent_change = underlying['percentChange']
    earnings.volume = underlying['totalVolume']
    earnings.quote_time = underlying['quoteTime']

    # Get data for the front term if non-regular.
    expi_list = []
    first_expi = first(sorted(chain.expis.items()))[1]
    if not is_regular_expiration(first_expi):
        expi_list.append(first_expi)

    # Get data for all regular expirations up to a maximum.
    for expi in find_regular_expirations(chain):
        if expi.info['daysToExpiration'] > config.max_dte:
            break
        expi_list.append(expi)

    # Process each fo the expirations.
    for expi in expi_list:
        if expi is not None:
            earnings.expirations.append(get_term(chain, expi, config))

    # Check volume.
    if earnings.volume < config.volume_threshold:
        earnings.diagnostics.append(
            f"WARNING: Low volume (less than {config.volume_threshold})")

    # Save the evaluation time.
    earnings.evaluation_time = datetime.datetime.now().isoformat()

    return earnings


def is_tradeable(earnings: pb.Earnings):
    """Return true if this earnings name has some tradeable expirations."""
    return (not earnings.diagnostics and
            any(not expi.diagnostics for expi in earnings.expirations))


def get_url(name: str) -> str:
    """Return a URL for searching for what the company does.."""
    return "https://www.google.com/search?q={}".format(
        urllib.parse.quote(get_clean_name(name)))


def render_index_to_html(outfile: io.IOBase):
    """Render a single HTML file with all the earnings."""

    # Render the index template.
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("overnight", ""),
        autoescape=jinja2.select_autoescape())
    index = env.get_template("index.html")
    outfile.write(index.render(date=datetime.date.today()))


def render_earnings_to_html(earlist: pb.EarningsList,
                            evaluation_time: datetime.datetime,
                            outfile: io.IOBase):
    """Render a single HTML file with all the earnings."""

    # Create an evaluation environment for the templates.
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("overnight", ""),
        autoescape=jinja2.select_autoescape())
    env.globals['get_url'] = get_url
    env.globals['get_clean_name'] = get_clean_name

    # Render the index template. The output is a single HTML file.
    index = env.get_template("overview.html")
    outfile.write(index.render(earlist=earlist,
                               evaluation_time=evaluation_time,
                               date=datetime.date.today()))


def render_files(symbols: List[str], config: pb.Config, earlist_all: pb.EarningsList,
                 output_dir: str):
    """Render all the output files to a directory."""

    # Create root dir.
    os.makedirs(output_dir, exist_ok=True)

    # Save the input config.
    with open(path.join(output_dir, "config.pbtxt"), "w") as outfile:
        print(config, file=outfile)

    # Write out the evaluated data.
    with open(path.join(output_dir, "earnings.pbtxt"), "w") as outfile:
        print(earlist_all, file=outfile)

    # Copy the input symbols.
    with open(path.join(output_dir, "symbols-all.csv"), "w") as outfile:
        wr = csv.writer(outfile)
        wr.writerows([(symbol,) for symbol in symbols])

    # Calculate evaluation time.
    evaluation_time = (
        parser.parse(max(earnings.evaluation_time
                         for earnings in earlist_all.earnings))
        .replace(microsecond=0))

    # Render to a single HTML page.
    with open(path.join(output_dir, "earnings-all.html"), "w") as outfile:
        render_earnings_to_html(earlist_all, evaluation_time, outfile)

    # Filter down the list to tradeable ones only and render to another page.
    earlist = pb.EarningsList()
    for earnings in earlist_all.earnings:
        if is_tradeable(earnings):
            earlist.earnings.append(earnings)
    with open(path.join(output_dir, "earnings.html"), "w") as outfile:
        render_earnings_to_html(earlist, evaluation_time, outfile)

    # Produce a watchlist for import of just the tradeable names.
    with open(path.join(output_dir, "symbols.csv"), "w") as outfile:
        wr = csv.writer(outfile)
        wr.writerow(['Symbol'])
        wr.writerows([[earnings.underlying] for earnings in earlist.earnings])

    # Render an index to all those files.
    with open(path.join(output_dir, "index.html"), "w") as outfile:
        render_index_to_html(outfile)


def fetch_chain(td: ameritrade.AmeritradeAPI, rate_limit, **kwargs):
    """Fetch a chain, with poor man's handling of rate limits."""

    # Fetch the option chain.
    while True:
        chain_json = td.GetOptionChain(**kwargs)

        # Half-assed recovery from rate limit hit.
        # TODO(blais): Properly handle this in the API code.
        if rate_limit:
            time.sleep(0.1)
        if ('error' in chain_json and
            re.search('transactions per seconds restriction reached',
                      chain_json['error'])):
            logging.warning("Rate-limit hit; throttling for 5 secs...")
            time.sleep(5)
            continue
        break
    return chain_json
