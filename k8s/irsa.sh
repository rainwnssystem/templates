eksctl create iamserviceaccount \
    --name <SERVICE_ACCOUNT_NAME> \
    --namespace <NS> \
    --cluster <CLUSTER_NAME> \
    --role-name <ROLE_NAME> \
    --attach-policy-arn <POLICY_ARN> \
    --approve \
    --override-existing-serviceaccounts