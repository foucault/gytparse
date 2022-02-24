#!/bin/bash

OVERLAY="/gr/oscillate/gytparse=$(pwd)/gytparse"
PYTHONPATH="$(pwd):${PYTHONPATH}"

G_RESOURCE_OVERLAYS=${OVERLAY} \
PYTHONPATH=${PYTHONPATH} \
LOCALRUN=1 \
  python _build/gytparse/gytparse
