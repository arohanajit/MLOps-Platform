#!/bin/bash

# Install k3s agent (worker)
curl -sfL https://get.k3s.io | K3S_URL="https://${master_ip}:6443" K3S_TOKEN="${node_token}" sh -s - agent 