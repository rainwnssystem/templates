################################################################################
# Add-on Toggles
################################################################################
locals {
  enable_argocd                       = false
  enable_argocd_image_updater         = false
  enable_calico                       = false
  enable_kube_prometheus_stack        = false
  enable_aws_gateway_api_controller   = false
  enable_karpenter                    = false
  enable_metrics_server               = true
  enable_cluster_autoscaler           = false
  enable_aws_load_balancer_controller = true
  enable_external_secrets             = false
  enable_aws_for_fluentbit            = false
  enable_fargate_fluentbit            = false
}

module "eks_blueprints_addons" {
  source  = "aws-ia/eks-blueprints-addons/aws"
  version = "1.24.3"

  cluster_name      = module.eks.cluster_name
  cluster_endpoint  = module.eks.cluster_endpoint
  cluster_version   = module.eks.cluster_version
  oidc_provider_arn = module.eks.oidc_provider_arn

  observability_tag = null

  eks_addons = {
    coredns = {
      most_recent = true
      configuration_values = jsonencode({
        replicaCount = 1
      })
    }
    vpc-cni = {
      most_recent = true
      configuration_values = jsonencode({
        env = merge(
          {
            # Security Groups for Pods
            ENABLE_POD_ENI                    = "true"
            POD_SECURITY_GROUP_ENFORCING_MODE = "standard"

            # Prefix Delegation
            ENABLE_PREFIX_DELEGATION = "true"
            WARM_PREFIX_TARGET       = "1"
          },
          local.enable_calico ? {
            ANNOTATE_POD_IP = "true"
            } : {
            NETWORK_POLICY_ENFORCING_MODE = "standard"
          }
        )
        enableNetworkPolicy = local.enable_calico ? "false" : "true"
      })
    }
    kube-proxy = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.irsa_ebs_csi_driver.arn
    }
    amazon-cloudwatch-observability = {
      most_recent              = true
      service_account_role_arn = module.irsa_cloudwatchagent.arn
      configuration_values = jsonencode({
        containerLogs = { enabled = false }
      })
    }
  }

  enable_argocd                       = local.enable_argocd
  enable_kube_prometheus_stack        = local.enable_kube_prometheus_stack
  enable_aws_gateway_api_controller   = local.enable_aws_gateway_api_controller
  enable_karpenter                    = local.enable_karpenter
  enable_metrics_server               = local.enable_metrics_server
  enable_cluster_autoscaler           = local.enable_cluster_autoscaler
  enable_aws_load_balancer_controller = local.enable_aws_load_balancer_controller
  enable_external_secrets             = local.enable_external_secrets
  enable_aws_for_fluentbit            = local.enable_aws_for_fluentbit
  enable_fargate_fluentbit            = local.enable_fargate_fluentbit

  ################################################################################
  # Kube Prometheus Stack
  ################################################################################
  kube_prometheus_stack = {
    values = [<<-EOF
      prometheus:
        prometheusSpec:
          scrapeInterval: "5s"
          evaluationInterval: "5s"
    EOF
    ]
  }

  ################################################################################
  # Argo CD
  ################################################################################
  argocd = {
    values = [<<-EOF
      configs:
        cm:
          timeout.reconciliation: 10s
    EOF
    ]
  }

  ################################################################################
  # AWS Load Balancer Controller
  ################################################################################
  aws_load_balancer_controller = {
    chart_version = "3.4.2"
    values = [<<-EOF
      replicaCount: 1
      vpcId: ${aws_vpc.this.id}
    EOF
    ]
    replace = true
  }

  ################################################################################
  # AWS Gateway API Controller
  ################################################################################
  aws_gateway_api_controller = {
    values = [<<-EOF
      clusterVpcId: ${aws_vpc.this.id}
      clusterName: ${module.eks.cluster_name}
      latticeEndpoint: ""
    EOF
    ]
  }

  ################################################################################
  # Metrics Server
  ################################################################################
  metrics_server = {
    replace = true
  }

  ################################################################################
  # Fargate Fluent Bit
  ################################################################################
  fargate_fluentbit_cw_log_group = {
    name            = "/aws/eks/${module.eks.cluster_name}/fargate"
    use_name_prefix = false
  }

  fargate_fluentbit = {
    flb_log_cw = true
  }

  ################################################################################
  # AWS for Fluent Bit
  ################################################################################
  aws_for_fluentbit_cw_log_group = {
    create = false
  }

  aws_for_fluentbit = {
    enable_containerinsights = true
    kubelet_monitoring       = true

    values = [<<-EOF
      hostNetwork: true
      dnsPolicy: ClusterFirstWithHostNet
      cloudWatchLogs:
        autoCreateGroup: true

      tolerations:
        - operator: Exists
    EOF
    ]

    role_policies = {
      CloudWatchFullAccess = "arn:aws:iam::aws:policy/CloudWatchFullAccess"
    }
  }

  ################################################################################
  # Cluster Autoscaler
  ################################################################################
  cluster_autoscaler = {
    values = [<<-EOF
      extraArgs:
        scan-interval: 10s
        scale-down-delay-after-add: 1m
        scale-down-delay-after-delete: 0s
        scale-down-delay-after-failure: 1m
        scale-down-unneeded-time: 1m
        node-deletion-delay-timeout: 1m
        node-deletion-batcher-interval: 0s
    EOF
    ]

    set = [{
      name  = "image.tag"
      value = "v1.36.0"
    }]
  }

  helm_releases = merge(
    #########################################################################
    # ArgoCD Image Updater
    #########################################################################
    local.enable_argocd && local.enable_argocd_image_updater ? {
      argocd-image-updater = {
        name             = "argocd-image-updater"
        repository       = "https://argoproj.github.io/argo-helm"
        chart            = "argocd-image-updater"
        chart_version    = "1.2.4"
        namespace        = "argocd"
        create_namespace = true

        values = [yamlencode({
          replicaCount       = 1
          createClusterRoles = false

          extraArgs = [
            "--interval",
            "5s"
          ]

          serviceAccount = {
            create = true
            name   = "argocd-image-updater"
            annotations = {
              "eks.amazonaws.com/role-arn" = module.irsa_argocd_updater.arn
            }
          }

          config = {
            "log.level" = "info"
            registries = [{
              name        = "ECR"
              api_url     = "https://${data.aws_caller_identity.caller.account_id}.dkr.ecr.${var.region}.amazonaws.com"
              prefix      = "${data.aws_caller_identity.caller.account_id}.dkr.ecr.${var.region}.amazonaws.com"
              ping        = true
              default     = true
              insecure    = false
              credentials = "ext:/scripts/ecr-login.sh"
              credsexpire = "11h"
            }]
          }

          authScripts = {
            enabled = true
            scripts = {
              "ecr-login.sh" = <<-EOT
                #!/bin/sh
                aws ecr --region "${var.region}" get-authorization-token --output text --query 'authorizationData[].authorizationToken' | base64 -d
              EOT
            }
          }
        })]
      }
    } : {},

    #########################################################################
    # Descheduler
    #########################################################################
    {
      # descheduler = {
      #   repository = "https://kubernetes-sigs.github.io/descheduler"
      #   chart      = "descheduler"

      #   name      = "descheduler"
      #   namespace = "kube-system"

      #   values = [<<-EOF
      #       kind: Deployment
      #       schedule: "* * * * *"
      #     EOF
      #   ]
      # }

      #########################################################################
      # Kyverno
      #########################################################################
      # kyverno = {
      #   repository = "https://kyverno.github.io/kyverno"
      #   chart      = "kyverno"
      #   name       = "kyverno"

      #   create_namespace = true
      #   namespace        = "kyverno"

      #   values = [<<-EOF
      #     admissionController:
      #       replicas: 1
      #     backgroundController:
      #       enabled: false
      #     cleanupController:
      #       enabled: false
      #     reportsController:
      #       enabled: false
      #     EOF
      #   ]
      # }
    }
  )
}

################################################################################
# Calico Network Policy
################################################################################
data "kubectl_file_documents" "calico_crds" {
  content = local.enable_calico ? file("${path.module}/../k8s/addons/calico/calico_install.yml") : ""
}

resource "kubectl_manifest" "calico_crds" {
  for_each = local.enable_calico ? data.kubectl_file_documents.calico_crds.manifests : {}

  yaml_body         = each.value
  server_side_apply = true
  force_conflicts   = true
  validate_schema   = false

  depends_on = [
    module.eks_blueprints_addons,
    kubernetes_cluster_role_binding_v1.aws_node_annotate_pod_ip,
  ]
}

resource "kubernetes_cluster_role_v1" "aws_node_annotate_pod_ip" {
  count = local.enable_calico ? 1 : 0

  metadata {
    name = "aws-node-annotate-pod-ip"
  }

  rule {
    api_groups = [""]
    resources  = ["pods"]
    verbs      = ["patch"]
  }

  depends_on = [module.eks_blueprints_addons]
}

resource "kubernetes_cluster_role_binding_v1" "aws_node_annotate_pod_ip" {
  count = local.enable_calico ? 1 : 0

  metadata {
    name = "aws-node-annotate-pod-ip"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.aws_node_annotate_pod_ip[0].metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = "aws-node"
    namespace = "kube-system"
  }
}

################################################################################
# Karpenter Node Role Output
################################################################################
output "node_iam_role_arn" {
  value = module.eks_blueprints_addons.karpenter.node_iam_role_arn
}
