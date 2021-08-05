#!/usr/bin/env make

TODAY ?= $(shell date +%Y%m%d)
SYMBOLS = $(HOME)/trading/earnings/earnings-$(TODAY).csv
OUTPUT_DIR = $(HOME)/trading/earnings/$(TODAY)

all:

protos: overnight/earnings_pb2.py

overnight/earnings_pb2.py: overnight/earnings.proto
	protoc -I . --python_out . --proto_path . $<

fetch:
	overnight-fetch --no-headless --output=$(SYMBOLS)

eval:
	overnight-eval -v --ameritrade-cache=/tmp/td --csv-filename=$(SYMBOLS) --output=$(OUTPUT_DIR)

conflicts:
	overnight-conflicts $(SYMBOLS)

share:
	publish-tmp earnings-$(TODAY) $(OUTPUT_DIR)
