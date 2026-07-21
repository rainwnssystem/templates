#!/bin/bash

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# EKS kubeconfig
aws eks update-kubeconfig --region $1 --name $2

# k9s
curl -sS https://webinstall.dev/k9s | bash
source ~/.config/envman/PATH.env