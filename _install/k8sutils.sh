#!/bin/bash

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# helm
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 get_helm.sh
./get_helm.sh
rm get_helm.sh

# EKS kubeconfig
aws eks update-kubeconfig --region $1 --name $2

# k9s
curl -sS https://webinstall.dev/k9s | bash
source ~/.config/envman/PATH.env

# calicoctl
curl -fsSL https://github.com/projectcalico/calico/releases/download/v3.32.1/calicoctl-linux-amd64 -o /tmp/calicoctl
chmod +x /tmp/calicoctl
sudo mv /tmp/calicoctl /usr/local/bin/calicoctl