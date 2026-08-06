- Prerequisites
  - Node security group Inbound: `node sg -> 15017`

- istioctl
```bash
curl -L https://istio.io/downloadIstio | sh -
cd istio-*
export PATH=$PWD/bin:$PATH
istioctl version --remote=false
```

- Gateway API CRD
```bash
kubectl get crd gateways.gateway.networking.k8s.io || \
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.5.1/standard-install.yaml
```

- Install
```bash
istioctl install --set profile=ambient -y   # ztunnel + CNI, sidecar 없음
istioctl install --set profile=default -y   # sidecar + ingress/egress gateway
istioctl install --set profile=minimal -y   # istiod only
```

- namespace 등록
```bash
kubectl label namespace <NAMESPACE> istio.io/dataplane-mode=ambient

# sidecar 모드는 Pod 재생성 필요
kubectl label namespace <NAMESPACE> istio-injection=enabled
kubectl rollout restart deployment -n <NAMESPACE>
```

- waypoint (ambient에서 L7 기능 사용 시)
```bash
istioctl waypoint apply -n <NAMESPACE> --enroll-namespace
kubectl get gateway -n <NAMESPACE>
```

- 확인
```bash
kubectl get pod -n istio-system
istioctl proxy-status
istioctl analyze -n <NAMESPACE>
istioctl proxy-config route deploy/<APP> -n <NAMESPACE>
```

- Uninstall
```bash
istioctl uninstall --purge -y
kubectl delete namespace istio-system
kubectl label namespace <NAMESPACE> istio.io/dataplane-mode-
kubectl label namespace <NAMESPACE> istio-injection-
```