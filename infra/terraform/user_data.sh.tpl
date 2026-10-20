#!/bin/bash
set -euxo pipefail
# Single-node k3s (includes Traefik ingress, local-path storage, metrics-server for the HPA)
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--tls-san ${public_ip} --write-kubeconfig-mode 644" sh -
# Swap gives the 4 GB node headroom during the OSM import job
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
