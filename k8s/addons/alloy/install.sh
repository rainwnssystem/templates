helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm upgrade -i alloy grafana/alloy --namespace <NAMESPACE> -f values.yaml