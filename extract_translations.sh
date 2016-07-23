#!/bin/bash

DOMAIN=minidlnaindicator
LOCALE_DIR=$(dirname $0)/locale

pygettext -d ${DOMAIN} -o ${LOCALE_DIR}/${DOMAIN}.pot minidlnaindicator.py
xdg-open ${LOCALE_DIR}/es/LC_MESSAGES/${DOMAIN}.po &
