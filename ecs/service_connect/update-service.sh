cat <<EOF > service-connect.json
{
	"serviceConnectConfiguration": {
		"enabled": true,
		"namespace": "internal",               // AWS Cloud Map ECS namespace
		"services": [
			{
				"portName": "app",                 // == ECS task definition portName
				"discoveryName": "product",        // AWS Cloud Map name
				// "ingressPortOverride": 8081,    // Override proxy port
				"clientAliases": [
					{
						"port": 80,                    // DNS port
						"dnsName": "product.internal"  // DNS name
					}
				]
			}
		]
	}
}
EOF

aws ecs update-service --cluster <CLUSTER_NAME> --service <SERVICE_NAME> --service-connect-configuration file://service-connect.json