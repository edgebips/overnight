# overnight: Earnings Trading Assistant

This projects supports manual trading of earnings plays on US equities.

It contains scripts to do the following:

- Fetch a generous list of symbols with AMC and BMO earnings symbols;

- Fetches options chains from TD Ameritrade to assess tradeability of each name
  and pre-calculate candidate strikes for a default strategy (a wide strangle in
  either the front month or the first regular expiration), based a multiple of
  the expected move. This serves as a quick and easy initial placement.

- Checks for conflicts between one's positions and the earnings list.

This is intended to be run first thing in the morning to support preparation for
earnings the next day, preparing a filterd list of names to check out, names
that share the right characteristics to be interesting enough (based on price,
volatility, magnitude of expected move, spreads, volume, etc.).
