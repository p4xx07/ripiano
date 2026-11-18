#!/bin/sh
# Trust X-Forwarded-For only from the reverse proxies in front of Ripiano, so the sign-in throttle sees the real
# client address without letting any other client choose its own. RIPIANO_TRUSTED_PROXIES is a space-separated list
# of addresses or CIDR ranges (for example the Raspberry Pi gateway: "192.168.1.10"). Docker's own networks and
# localhost (the Synology reverse proxy on the same NAS reaches the container through them) are always trusted.
set -eu
out=/etc/nginx/conf.d/00-real-ip.conf
{
  echo "real_ip_header X-Forwarded-For;"
  echo "real_ip_recursive on;"
  for source in 127.0.0.1 ::1 172.16.0.0/12 ${RIPIANO_TRUSTED_PROXIES:-}; do
    case "$source" in
      *[!0-9a-fA-F.:/]*) echo "real-ip: ignoring invalid RIPIANO_TRUSTED_PROXIES entry: $source" >&2 ;;
      *) echo "set_real_ip_from $source;" ;;
    esac
  done
} > "$out"
