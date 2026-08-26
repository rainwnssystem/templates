
kubectl debug --image alpine -itn skills myapp-64f576fbc6-jx4zk -- /bin/ash -c 'apk add ngrep && ngrep -d ens5 -s 0 -W byline port 8080'