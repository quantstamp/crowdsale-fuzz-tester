#!/bin/bash

NUM_TESTS=10

for i in `seq 1 ${NUM_TESTS}`
do
    python3 crowdsale_fuzzer/fuzzer.py
done
