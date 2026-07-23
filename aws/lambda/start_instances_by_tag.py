import json
import boto3
client = boto3.client('ec2')

def lambda_handler(event, context):

    response = client.describe_instances(
        DryRun=False,
        Filters=[
            {'Name':'tag:ssm', 'Values':['true']},  # instance를 찾을 tag
        ]
    )
    
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            print(instance['InstanceId'])
            response = client.start_instances(
                InstanceIds=[
                    instance['InstanceId']
                ]
            )
            
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
