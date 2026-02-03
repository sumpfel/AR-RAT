#!/bin/bash
echo "=== UART Diagnostic Tool ==="
echo "Date: $(date)"

echo -e "\n1. Checking User Groups (is user in dialout?):"
groups

echo -e "\n2. Checking Serial Devices:"
ls -l /dev/serial* /dev/ttyAMA* 2>/dev/null

echo -e "\n3. Checking specific permissions:"
ls -l /dev/ttyAMA10 2>/dev/null
ls -l /dev/serial0 2>/dev/null

echo -e "\n4. Checking cmdline.txt (Is console using serial?):"
cat /boot/firmware/cmdline.txt 2>/dev/null || cat /boot/cmdline.txt

echo -e "\n5. Checking config.txt (overlays):"
grep -E "dtoverlay|enable_uart|uart" /boot/firmware/config.txt 2>/dev/null || grep -E "dtoverlay|enable_uart|uart" /boot/config.txt

echo -e "\n6. Checking running processes using tty:"
lsof /dev/ttyAMA10 2>/dev/null
lsof /dev/serial0 2>/dev/null

echo -e "\n=== End of Diagnostics ==="
