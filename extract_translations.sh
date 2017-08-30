#!/usr/bin/env bash

DOMAIN=minidlnaindicator
LOCALE_DIR=$(dirname $0)/minidlnaindicator/locale
POT_FILE=${LOCALE_DIR}/${DOMAIN}.pot

[ ! -d "${LOCALE_DIR}" ] && mkdir "${LOCALE_DIR}"

export PYTHONPATH=$(dirname $0)
pybabel extract -F $(dirname $0)/babel.cfg -o ${POT_FILE} .

for i in $(find minidlnaindicator/locale -mindepth 1 -maxdepth 1 -type d); do

	DIR_LANG=$(basename ${i})
    PO_FILE=${LOCALE_DIR}/${DIR_LANG}/LC_MESSAGES/${DOMAIN}.po
    if [ -f  ${PO_FILE} ] ; then
        pybabel update -i ${POT_FILE} -D ${DOMAIN} -d ${LOCALE_DIR} -l ${DIR_LANG}
    else
        pybabel init -i ${POT_FILE} -D ${DOMAIN} -d ${LOCALE_DIR} -l ${DIR_LANG}
    fi
    LANG=C xdg-open ${LOCALE_DIR}/${DIR_LANG}/LC_MESSAGES/${DOMAIN}.po &

done
