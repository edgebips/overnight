from typing import Optional

import click

from goodkids import session as sesslib
from goodkids import utils
from johnny.base.etl import petl
from johnny.sources.tastyworks_csv import symbols as twsym


def get_position_underlyings(session: sesslib.Session):
    """Fetch the list of position underlyings from Tastyworks."""

    # Get the account.
    accounts = utils.get_accounts(session)

    # Find the set of underlyings for which I have a position.
    position_underlyings = set()
    for account in accounts:
        accid = account['account-number']
        resp = session.relget(f'/accounts/{accid}/positions')
        for position in utils.get_data(resp)['items']:
            inst = twsym.ParseSymbol(position['symbol'])
            position_underlyings.add(inst.underlying)

    return position_underlyings
