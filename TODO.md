- Convert the output to a series of proto objects
- Separate the rendering stage, write out to HTML


- Check the spreads.
- Skip names with no options.
- Check the further terms if the options are too cheap.
- Check the term structure of IV.
- Add info about the term structure.
- Check the volume.
- Check the IVR.
- Add info about skew.
- If a third strike isn't available for em_straddle, make it zero.
- Warn on too small a strangle opportunity
- Add stats about the prior earnings, like E*Trade.
- Spread elimination should be an average of all the strikes up to the one I'm trying to trade
- Filter out strikes at below 4 deltas, their spreads are out-of-whack.
- Also look at the price of the strangle one strike in, to avoid too harsh filtering on that.
