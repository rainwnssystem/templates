import json
import boto3
from uuid import uuid4
import datetime
import base64

def lambda_handler(event, context):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('<TABLE_NAME>')

    print(f'event: {event}')

    method = event['http_method']
    path = event['path']

    if path.endswith('users'):
        if method == 'GET':

            if event['id'] == "":
                return { 'statusCode': 400 }

            id = event['id']

            response = table.get_item(
                Key={
                    'id': id
                }
            )
            
            if 'Item' not in response:
                return { 'statusCode': 404 }

            data = response['Item']

            return {
                'statusCode': 200,
                'body': {
                    "id": id,
                    "name": data['name'],
                    "age": int(data['age'])
                }
            }

        if method == 'POST':

            if event['name'] == "" or event['age'] == "":
                return { 'statusCode': 400 }

            id = str(uuid4())
            name = event['name']
            age = int(event['age'])

            now = datetime.datetime.now()
            epoch = str(int(now.timestamp() * 1000))


            response = table.put_item(
                Item = {
                    'id': id,
                    'name': name,
                    'age': age,
                    'timestamp': epoch
                }
            )

            return {
                'statusCode': 201,
                'body': {
                    'id': id,
                    'name': name,
                    'age': age,
                    'timestamp': epoch
                }
            }


    return {
        'statusCode': 400
    }