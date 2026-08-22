kubectl patch hpa product-hpa -n wsi -p '{"spec":{"maxReplicas":1}}'
kubectl delete nodeclaim --all