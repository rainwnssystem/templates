import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('name')

# GetItem (PK, SK)
response = table.get_item(
    Key={
        'string': 'string'
    }
)
data = response['Item']
id = data['id']


# PutItem
response = table.put_item(
    Item={
        'string': 'string'
    }
)

# Query (PK)
import datetime
from boto3.dynamodb.conditions import Key

response = table.query(
    KeyConditionExpression=Key('id').eq('id123'),  # Sort key
)