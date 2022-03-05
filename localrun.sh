#!/bin/bash

OVERLAY="/gr/oscillate/gytparse=$(pwd)/gytparse"
PYTHONPATH="$(pwd):${PYTHONPATH}"

G_RESOURCE_OVERLAYS=${OVERLAY} \
PYTHONPATH=${PYTHONPATH} \
  python _build/gytparse/gytparse
