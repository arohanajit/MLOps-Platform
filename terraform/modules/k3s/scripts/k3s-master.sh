#!/bin/bash

# Install k3s server (master)
curl -sfL https://get.k3s.io | K3S_TOKEN="${node_token}" sh -s - server \
    --disable traefik \
    --disable servicelb \
    --node-taint node-role.kubernetes.io/master=true:NoSchedule

# Wait for k3s to be ready
until kubectl get node >/dev/null 2>&1; do
    sleep 1
done

# Install AWS cloud provider components
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: aws-secret
  namespace: kube-system
stringData:
  key_id: ${aws_access_key_id}
  access_key: ${aws_secret_access_key}
EOF

# Install MetalLB for load balancing
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.7/config/manifests/metallb-native.yaml
kubectl wait --namespace metallb-system \
  --for=condition=ready pod \
  --selector=app=metallb \
  --timeout=90s 