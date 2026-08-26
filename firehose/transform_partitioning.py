import base64
import json
from datetime import datetime

def lambda_handler(event, context):
    output = []

    for record in event['records']:
        print(record['recordId'])
        payload = base64.b64decode(record['data']).decode('utf-8')

        # Do custom processing on the payload here
        data = json.loads(payload)
        total = data['amount'] * data['price']
        data['total_price'] = total
        
        event_time = datetime.today()
        partition_keys = {
            "year": event_timestamp.strftime('%Y'),
            "month": event_timestamp.strftime('%m'),
            "day": event_timestamp.strftime('%d'),
            "hour": event_timestamp.strftime('%H'),
            "minute": event_timestamp.strftime('%M')
        }

        output_record = {
            'recordId': record['recordId'],
            'result': 'Ok',
            'data': base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8'),
            'metadata': {
                'partitionKeys': partition_keys
            }
        }
        output.append(output_record)

    return {'records': output}