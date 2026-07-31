#!/usr/bin/env bash
# Start the Win11 test VM for ClipMark Windows testing.
#
# Usage:
#   ./scripts/start-win11-test-vm.sh
#   virt-viewer win11
#
# Inside the VM:
#   1. Copy or git clone ClipMark into the guest
#   2. Double-click setup.bat
#   3. Double-click run.bat

set -euo pipefail

LIBVIRT_URI="qemu:///system"
DOMAIN="win11"
DISK="/var/lib/libvirt/images/win11.qcow2"

if [[ ! -f "${DISK}" ]]; then
  echo "Win11 disk not found: ${DISK}" >&2
  exit 1
fi

if ! virsh -c "${LIBVIRT_URI}" dominfo "${DOMAIN}" >/dev/null 2>&1; then
  echo "Libvirt domain '${DOMAIN}' not found on ${LIBVIRT_URI}." >&2
  echo "Open virt-manager and import ${DISK}, or see scripts/win11-test-vm.md." >&2
  exit 1
fi

STATE="$(virsh -c "${LIBVIRT_URI}" dominfo "${DOMAIN}" | awk -F': ' '/^State:/ {print $2}')"
if [[ "${STATE}" == "running" ]]; then
  echo "Domain '${DOMAIN}' is already running."
else
  echo "Starting domain: ${DOMAIN}"
  virsh -c "${LIBVIRT_URI}" start "${DOMAIN}"
fi

echo
echo "Open the VM console:"
echo "  virt-viewer ${DOMAIN}"
echo "or:"
echo "  virt-manager"
echo
echo "Inside Windows, test ClipMark:"
echo "  1. git clone or copy this folder to the VM"
echo "  2. Double-click setup.bat"
echo "  3. Double-click run.bat"
