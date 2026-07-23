from __future__ import print_function
import base64
import json
import datetime

def lambda_handler(firehose_records_input, context):
    print("Received records for processing from DeliveryStream: " + firehose_records_input['deliveryStreamArn']
          + ", Region: " + firehose_records_input['region']
          + ", and InvocationId: " + firehose_records_input['invocationId'])

    # Create return value.
    firehose_records_output = {'records': []}

    for firehose_record_input in firehose_records_input['records']:
        # Decode the base64 data
        payload = base64.b64decode(firehose_record_input['data'])
        json_value = json.loads(payload)

        print("Record that was received")
        print(json_value)
        print("\n")

        # Parse the timestamp and extract date-time components
        event_timestamp = datetime.datetime.strptime(json_value['timestamp'], '%Y-%m-%dT%H:%M:%S%z')
        json_value['year'] = event_timestamp.year
        json_value['month'] = event_timestamp.month
        json_value['day'] = event_timestamp.day
        json_value['hour'] = event_timestamp.hour
        json_value['minute'] = event_timestamp.minute
        json_value['second'] = event_timestamp.second

        # Convert processingtime from string with unit to float in milliseconds
        processing_time_str = json_value['processingtime']
        processing_time_ms = round(float(processing_time_str[:-2]) / 1000, 3)

        json_value['processingtime'] = processing_time_ms
        json_value['responsecode'] = int(json_value['responsecode'])

        # Re-encode the modified JSON back to base64
        modified_payload = base64.b64encode(json.dumps(json_value).encode('utf-8')).decode('utf-8')

        print(json_value)

        # Set partition keys
        partition_keys = {
            "year": str(json_value['year']),
            "month": str(json_value['month']),
            "day": str(json_value['day']),
            "hour": str(json_value['hour']),
            "minute": str(json_value['minute']),
            "second": str(json_value['second'])
        }

        # Create output Firehose record
        firehose_record_output = {
            'recordId': firehose_record_input['recordId'],
            'data': modified_payload,
            'result': 'Ok',
            'metadata': {'partitionKeys': partition_keys}
        }

        # Add the record to the list of output records
        firehose_records_output['records'].append(firehose_record_output)

    # Return processed records
    return firehose_records_output
