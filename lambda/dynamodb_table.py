import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('name')

response = table.get_item(
    Key={
        'string': 'string'
    }
)

response = table.put_item(
    Item={
        'string': 'string'
    }
)