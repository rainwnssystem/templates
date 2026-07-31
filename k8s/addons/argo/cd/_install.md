- argocd-values.yml
```yaml
configs:
  cm:
    timeout.reconciliation: 10s
  params:
    server.insecure: true
```

- argocd cli
```bash
curl -sSL -o argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
sudo install -m 555 argocd-linux-amd64 /usr/local/bin/argocd
rm argocd-linux-amd64
```

- Install argocd
```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update argo

helm install argocd argo/argo-cd \
    --create-namespace \
    --namespace argocd \
    --values values.yaml
```