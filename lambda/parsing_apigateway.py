import json
import base64

def lambda_handler(event, context):

    print(event)

    # HTTP
    method = event['requestContext']['http']['method']

    # Query string
    email = event['queryStringParameters']['email']
    name = event['queryStringParameters']['name']

    # Request body
    body = json.loads(base64.b64decode(event['body']))
    order = body['order']


    return {
        'statusCode': 200,
        'body': {
            "email": email,
            "name": name,
            "order": order
        }
    }