| Subnet | CIDR | 비고 |
|---|---|---|
| VPC | `10.0.0.0/16` | |
| fw | `10.0.0.0/24` | NFW 엔드포인트(`vpce-fw`)만 |
| public | `10.0.1.0/24` | NAT GW |
| private | `10.0.2.0/24` | EC2 |

---

## 1. IGW → NAT → NFW → EC2

> 방화벽이 **EC2 사설 IP**를 봄 · 인스턴스 단위 5-tuple 룰 가능

```
in    IGW ──▶ NAT ──▶ NFW ──▶ EC2
out   EC2 ──▶ NFW ──▶ NAT ──▶ IGW
```

| # | Route Table | 연결 | Destination | Target |
|---|---|---|---|---|
| 1 | `igw-edge-rt` | — | — | **설정 불필요** |
| 2 | `public-rt` | `10.0.1.0/24` | `10.0.0.0/16`<br>`10.0.2.0/24`<br>`0.0.0.0/0` | local<br>**`vpce-fw`** ★<br>`igw-xxxx` |
| 3 | `fw-rt` | `10.0.0.0/24` | `10.0.0.0/16`<br>`0.0.0.0/0` | local<br>`nat-xxxx` |
| 4 | `private-rt` | `10.0.2.0/24` | `10.0.0.0/16`<br>`0.0.0.0/0` | local<br>`vpce-fw` |

★ local보다 구체적인 경로 · 목적지는 subnet CIDR과 정확히 일치 · private subnet 늘면 줄 추가

---

## 2. IGW → NFW → NAT → EC2

> 출발지가 **NAT GW IP**로 뭉개짐 · 도메인/목적지 기반 룰 + 인바운드 검사

```
in    IGW ──▶ NFW ──▶ NAT ──▶ EC2
out   EC2 ──▶ NAT ──▶ NFW ──▶ IGW
```

| # | Route Table | 연결 | Destination | Target |
|---|---|---|---|---|
| 1 | `igw-edge-rt` | IGW (edge assoc) | `10.0.0.0/16`<br>`10.0.1.0/24` | local<br>**`vpce-fw`** ★ |
| 2 | `fw-rt` | `10.0.0.0/24` | `10.0.0.0/16`<br>`0.0.0.0/0` | local<br>`igw-xxxx` |
| 3 | `public-rt` | `10.0.1.0/24` | `10.0.0.0/16`<br>`0.0.0.0/0` | local<br>`vpce-fw` |
| 4 | `private-rt` | `10.0.2.0/24` | `10.0.0.0/16`<br>`0.0.0.0/0` | local<br>`nat-xxxx` |

★ 없으면 복귀가 IGW→NAT 직행 = 비대칭 · public에 ALB/EIP 있으면 그 CIDR도 추가

---

## 공통

- AZ마다 fw/public/private subnet + RT 3벌, **같은 AZ `vpce`만** 지정
- fw subnet에 다른 리소스 배치 금지 (같은 subnet 트래픽 검사 불가)
- NFW는 NAT 안 함 · 왕복이 같은 엔드포인트를 지나야 함
- 순서: subnet → NFW 생성(`vpce` 확인) → `fw-rt` → `public/private-rt` → `igw-edge-rt`
