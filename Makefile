#!/usr/bin/env make

TODAY ?= $(shell date +%Y%m%d)
OUTPUT = $(HOME)/p/overnight-data/earnings/$(TODAY)
SYMBOLS = $(OUTPUT)/fetch.csv

all:

protos: overnight/earnings_pb2.py

overnight/earnings_pb2.py: overnight/earnings.proto
	protoc -I . --python_out . --proto_path . $<

fetch:
	overnight-fetch --no-headless --output=$(SYMBOLS)

clear:
	-rm -rf /tmp/td

eval: clear
	overnight-eval -v --ameritrade-cache=/tmp/td --csv-filename=$(SYMBOLS) --output=$(OUTPUT)

reeval:
	overnight-eval -v --ameritrade-cache=/tmp/td --csv-filename=$(SYMBOLS) --output=$(OUTPUT)

conflicts:
	overnight-conflicts $(SYMBOLS)

share:
	publish-tmp earnings-$(TODAY) $(OUTPUT)

movers:
	overnight-movers --ameritrade-cache=/tmp/td --threshold=0.02
