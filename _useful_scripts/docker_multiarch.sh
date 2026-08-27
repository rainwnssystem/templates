while true; do
  if [ -f /proc/sys/fs/binfmt_misc/qemu-aarch64 ]; then
    break
  fi

  docker run --privileged --rm tonistiigi/binfmt --install arm64
done

docker buildx build --platform linux/amd64,linux/arm64 -t app:latest --push .