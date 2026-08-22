echo global:
  scrape_interval: 30s

scrape_configs:
  - job_name: 'ec2-node-exporter'
    static_configs:
      - targets:
          - '10.0.10.194:9100'
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
      - target_label: compute_platform
        replacement: 'ec2'

aws amp create-scraper \
  --alias "wsi-ec2-metrics-scraper" \
  --source vpcConfiguration="{subnetIds=['<SUBNET_ID>','<SUBNET_ID>'], securityGroupIds=['<SG_ID>'] }" \
  --scrape-configuration configurationBlob=$(cat scrape-config.yaml | base64 -w 0) \
  --destination ampConfiguration="{workspaceArn='<WORKSPACE_ARN>'}"