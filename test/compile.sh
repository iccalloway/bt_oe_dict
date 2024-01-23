#!/bin/bash
python3 process.py
cd ..
make
make install
cd test/
