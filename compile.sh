#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/oe_templates"
make clean
make
make install
