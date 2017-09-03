#!/bin/bash

# Original from https://gist.github.com/thefekete/d0d7195783b216e0d67a6d56f19207ee
# With gnome shell restart from https://github.com/brunelli/gnome-shell-extension-installer/blob/master/gnome-shell-extension-installer

usage="
usage:
    $(basename $0) install <extension-uuid> [<extension-id/uuid> ... ]
    $(basename $0) remove <extension-uuid> [<extension-id/uuid> ... ]
    $(basename $0) help

commands:

    install     install the extension(s) identified by <extension-uuid> 
    remove      remove the extension(s) identified by <extension-uuid> 
    help        print this message and exit

Given a gnome extension UUID, $(basename $0) will retrieve the extension
from extensions.gnome.org and install it to the users home directory. The
UUID is something like drop-down-terminal@gs-extensions.zzrough.org or
refresh-wifi@kgshank.net.
"

# prerequisites
which gnome-shell >/dev/null || (echo "command not found: gnome-shell"; exit 1)
which gnome-shell-extension-tool >/dev/null || (echo "command not found: gnome-shell-extension-tool"; exit 1)
which curl >/dev/null || (echo "command not found: curl"; exit 1)
which jq >/dev/null || (echo "command not found: jq"; exit 1)

gv=$(gnome-shell --version | cut -d' ' -f3)
BASE_URL="https://extensions.gnome.org"

install () {

    # args: the uuid to download to
    UUID="$1"

    echo "Fetching extension information..."
    INFO_URL="${BASE_URL}/extension-info/?uuid=${UUID}&shell_version=${gv}"
    EXT_INFO_FILE=$(mktemp)
    OUT=$(curl -fsS -o "${EXT_INFO_FILE}" "${INFO_URL}" 2>&1)
    RET=$?
    if [ $RET -ne 0 ]; then
        echo "Error getting information (${RET}): ${OUT}"
        rm -f "${EXT_INFO_FILE}"
        return 1
    fi

    DOWNLOAD_URL=$(jq -r '.download_url' "${EXT_INFO_FILE}" 2>&1)
    RET=$?
    if [ $RET -ne 0 ]; then
        echo "Error fetching download information (${RET}): ${DOWNLOAD_URL}"
        rm -f "${EXT_INFO_FILE}"
        return 1
    elif [[ -z "${DOWNLOAD_URL}" || "${DOWNLOAD_URL}" == "null" ]]; then
        echo "No download URL found for extension"
        rm -f "${EXT_INFO_FILE}"
        return 1
    fi
    rm -f "${EXT_INFO_FILE}"
    DOWNLOAD_URL="${BASE_URL}${DOWNLOAD_URL}"

    echo "Downloading extension..."
    EXT_DEST_ZIP=$(mktemp)
    OUT=$(curl -fsSL -o "${EXT_DEST_ZIP}" "${DOWNLOAD_URL}" 2>&1)
    RET=$?
    if [ ${RET} -ne 0 ]; then
        echo "Error downloading file (${RET}): ${OUT}"
        rm -f "${EXT_DEST_ZIP}"
        return 1
    fi

    echo "Cleaning old extension..."
    EXT_DEST_DIR="$HOME/.local/share/gnome-shell/extensions/${UUID}"
    rm -Rf "${EXT_DEST_DIR}"
    mkdir -p "${EXT_DEST_DIR}"

    echo "Installing extension..."
    OUT=$(unzip -q -o -d "${EXT_DEST_DIR}" "${EXT_DEST_ZIP}" 2>&1)
    RET=$?
    if [ ${RET} -ne 0 ]; then
        echo "Error uncompressing file (${RET}): ${OUT}"
        rm -f "${EXT_DEST_ZIP}"
        return 1
    fi
    rm -f "${EXT_DEST_ZIP}"

    gnome-shell-extension-tool -e "${UUID}"

    if [[ $( pgrep gnome-shell ) ]]; then
        echo "Restarting GNOME Shell..."
        dbus-send --session --type=method_call \
                  --dest=org.gnome.Shell /org/gnome/Shell \
                  org.gnome.Shell.Eval string:"global.reexec_self();"
    fi

    return 0

}

remove () {

    UUID="$1"
    EXT_DIR="${HOME}/.local/share/gnome-shell/extensions/${UUID}"
    if [ ! -e "${EXT_DIR}" ]; then
        echo "Extension not found"
        return 1
    fi

    gnome-shell-extension-tool -d "$UUID"
    rm -rf "${EXT_DIR}"

    if [[ $( pgrep gnome-shell ) ]]; then
        echo "Restarting GNOME Shell..."
        dbus-send --session --type=method_call \
                  --dest=org.gnome.Shell /org/gnome/Shell \
                  org.gnome.Shell.Eval string:"global.reexec_self();"
    fi

    return 0

}

ACTION=$1
EXTENSION=$2

if [ -z "${ACTION}" ]; then
    echo "No action specified".
    echo "$usage"
    exit 1
fi

if [ -z "${EXTENSION}" ]; then
    echo "No extension specified".
    echo "$usage"
    exit 1
fi

if [ "${ACTION}" == "help" ]; then
    echo "$usage"
    exit 0
elif [ "${ACTION}" == "install" ]; then
    install "${EXTENSION}"
    exit $?
elif [ "${ACTION}" == "remove" ]; then
    remove "${EXTENSION}"
    exit $?
else
    echo "Unknown action"
    echo "$usage"
    exit 1
fi
