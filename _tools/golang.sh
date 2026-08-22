#!/bin/bash

GO_VERSION="1.26.3"
ARCH="amd64"  # amd64 | arm64

curl -LO "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz"

sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf "go${GO_VERSION}.linux-${ARCH}.tar.gz"

rm "go${GO_VERSION}.linux-${ARCH}.tar.gz"

cat >> ~/.bashrc <<PROFILE
export PATH=/usr/local/go/bin:$HOME/go/bin:$PATH
PROFILE

source ~/.bashrc