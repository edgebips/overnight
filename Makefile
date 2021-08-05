#!/usr/bin/env make

TODAY = $(shell date +%Y%m%d)
EARNINGS_TODAY = $(HOME)/trading/earnings/earnings-$(TODAY).csv
EARNINGS_OUTPUT = $(HOME)/trading/earnings/earnings-$(TODAY)

all:

protos: overnight/earnings_pb2.py

overnight/earnings_pb2.py: overnight/earnings.proto
	protoc -I . --python_out . --proto_path . $<

fetch overnight-fetch:
	overnight-fetch --no-headless --output=$(EARNINGS_TODAY)

# Note: Rate-limit the first one, and not the second.
# TODO(blais): Handle rate limiting in the API.
overnight: $(EARNINGS_TODAY:.csv=.overnight_all) $(EARNINGS_TODAY:.csv=.overnight)

# $(EARNINGS_TODAY:.csv=.overnight_all):
# 	overnight -r -n --ameritrade-cache=/tmp/td -v --csv-filename=$(EARNINGS_TODAY) --output=$(EARNINGS_OUTPUT) | tee $(EARNINGS_TODAY:.csv=.overnight_all)

$(EARNINGS_TODAY:.csv=.overnight):
	overnight --ameritrade-cache=/tmp/td -v --csv-filename=$(EARNINGS_TODAY) --output=$(EARNINGS_OUTPUT)
