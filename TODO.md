- Create high-level index with one-liners with basic stats, drill down in page
- Sort down by volume
- Have a price history chart rendered on each page

- Spread elimination should be an average of all the strikes up to the one I'm trying to trade.
- Check the term structure of IV; Add info about the term structure too.
- Check the IVR.
- Add info about skew.
- Fetch details stats about the prior moves after prior earnings, for each name.
- Filter out strikes at below 4 deltas, their spreads are out-of-whack.
- Also look at the price of the strangle one strike in, to avoid too harsh filtering on that.
- Add AMC & BMO per symbol.
- Create a script to check for outlier moves after hours automatically, and warn.
  Normalize the move in terms of EM.
- Compute statistics over each season and time period.
- Simulate the effect of buying protection.
- Attempt to use the skew or any other data to see if it is predictive at all.

- Translate strikes to account for skew
- Report skew
- Include IVR and IVx'es in full report
- Render a chart of render stock price moves against normal dist
- Add volume by IV

- Looks at IVx differential
- Looks at IVR (if possible)
- Looks at TW's liquidity rating
- Looks at prior moves on earnings
- We also need a tool to monitor post-close / pre-open prices and the positions I took.

- Use this cheap source of past dates
  https://finance.yahoo.com/calendar/earnings?symbol=AMAT
  with the TD API to fetch histo stock prices and calculate actual moves.

- Present term structure (see goodkids/bin/tastyworks-metrics).


## Tool: Pre-market Moves

Write a script that
- Fetches my positions
- Looks for last close
- Looks for current EXT bid/ask
- Warns on moves in excess of IV (in terms of IV)
- Report "largest post-market moves".
