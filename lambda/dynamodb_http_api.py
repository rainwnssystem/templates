import json
import boto3
from uuid import uuid4
import datetime
import base64

def lambda_handler(event, context):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('project-table')

    print(f'event: {event}')

    method = event['requestContext']['http']['method']
    path = event['requestContext']['http']['path']

    if path.endswith('users'):
        if method == 'GET':

            if 'queryStringParameters' not in event:
                return { 'statusCode': 400 }

            params = event['queryStringParameters']

            if 'id' not in params:
                return { 'statusCode': 400 }

            id = params['id']

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
                'body': json.dumps({
                    "id": id,
                    "name": data['name'],
                    "age": int(data['age'])
                })
            }

        if method == 'POST':

            body = json.loads(event['body'])
            print(body)

            if 'name' not in body or 'age' not in body:
                return { 'statusCode': 400 }

            id = str(uuid4())
            name = body['name']
            age = int(body['age'])

            now = datetime.datetime.now()
            epoch = str(int(now.timestamp() * 1000))
            
            print(f'{id}, {name}, {age}, {epoch}')

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
                'body': json.dumps({
                    'id': id,
                    'name': name,
                    'age': age,
                    'timestamp': epoch
                })
            }


    return {
        'statusCode': 400
    }