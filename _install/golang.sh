#!/bin/bash

GO_VERSION="1.26.3"
curl -LO "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz"

sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf "go${GO_VERSION}.linux-amd64.tar.gz"

rm "go${GO_VERSION}.linux-amd64.tar.gz"

cat >> ~/.bashrc << 'PROFILE'
export PATH=/usr/local/go/bin:$HOME/go/bin:$PATH
PROFILE

source ~/.bashrc