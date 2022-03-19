#!/bin/bash

OVERLAY="/gr/oscillate/gytparse=$(pwd)/data"
PYTHONPATH="$(pwd):${PYTHONPATH}"

glib-compile-schemas data --targetdir=$(pwd)

GSETTINGS_SCHEMA_DIR="$(pwd):${GSETTINGS_SCHEMA_DIR}" \
G_RESOURCE_OVERLAYS=${OVERLAY} \
PYTHONPATH=${PYTHONPATH} \
  python _build/gytparse/gytparse
