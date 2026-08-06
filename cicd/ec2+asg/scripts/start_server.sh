#!/bin/bash
set -e

chmod +x /opt/wsi-product/product

cp /opt/wsi-product/product.service /etc/systemd/system/product.service
systemctl daemon-reload
systemctl enable --now product