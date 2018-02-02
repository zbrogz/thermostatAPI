import boto3
import os
import json
from uuid import uuid4 as Uuid
import decimal

modes = ["off", "heat", "cool", "normal", "eco"]
fan_modes = ["on", "auto"]


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def state_table():
    return boto3.resource('dynamodb').Table(os.environ['STATE_TABLE_NAME'])


def get_thermostat(uuid):
    thermostat = state_table().get_item(Key={'uuid': uuid})
    response = {
        'isBase64Encoded': 'false',
        'statusCode': 200,
        'body': json.dumps(thermostat['Item'], cls=DecimalEncoder)
    }
    return response


def get_all_thermostats():
    thermostats = state_table().scan()
    response = {
        'isBase64Encoded': 'false',
        'statusCode': 200,
        'body': json.dumps(thermostats['Items'], cls=DecimalEncoder)
    }
    return response


def create_thermostat(thermostat_data):
    if (not thermostat_data['area'] or not
            isinstance(thermostat_data['area'], str)):
        raise Exception('Error. Must specify area.')
    if (not thermostat_data['hvac_url'] or not
            isinstance(thermostat_data['hvac_url'], str)):
        raise Exception('Error. Must specify hvac_url.')
    if (not thermostat_data['temperature_url'] or not
            isinstance(thermostat_data['temperature_url'], str)):
        raise Exception('Error. Must specify temperature_url.')

    uuid = Uuid().hex
    state = {
        'uuid': uuid,
        'area': thermostat_data['area'],
        'hvac_url': thermostat_data['hvac_url'],
        'temperature_url': thermostat_data['temperature_url'],
        'desired_temperature': 70,
        'eco_min_temperature': 65,
        'eco_max_temperature': 78,
        'tolerance': 1,
        'mode': 'normal',
        'fan': 'auto'
    }
    state_table().put_item(Item=state)
    response = {
        'isBase64Encoded': 'false',
        'statusCode': 200,
        'body': json.dumps(state)
    }
    return response


def update_thermostat(uuid, thermostat_data):
    updateExpressions = []
    attributeValues = {}
    expressionAttributeNames = {}
    if 'area' in thermostat_data and isinstance(thermostat_data['area'], str):
        updateExpressions.append("area = :a")
        attributeValues[':a'] = thermostat_data['area']
    if ('hvac_url' in thermostat_data and
            isinstance(thermostat_data['hvac_url'], str)):
        updateExpressions.append("hvac_url = :h")
        attributeValues[':h'] = thermostat_data['hvac_url']
    if ('temperature_url' in thermostat_data and
            isinstance(thermostat_data['temperature_url'], str)):
        updateExpressions.append("temperature_url = :t")
        attributeValues[':t'] = thermostat_data['temperature_url']
    if ('desired_temperature' in thermostat_data and
            isinstance(thermostat_data['desired_temperature'], int)):
        updateExpressions.append("desired_temperature = :d")
        attributeValues[':d'] = thermostat_data['desired_temperature']
    if ('eco_min_temperature' in thermostat_data and
            isinstance(thermostat_data['eco_min_temperature'], int)):
        updateExpressions.append("eco_min_temperature = :e")
        attributeValues[':e'] = thermostat_data['eco_min_temperature']
    if ('eco_max_temperature' in thermostat_data and
            isinstance(thermostat_data['eco_max_temperature'], int)):
        updateExpressions.append("eco_max_temperature = :x")
        attributeValues[':x'] = thermostat_data['eco_max_temperature']
    if ('tolerance' in thermostat_data and
            isinstance(thermostat_data['tolerance'], int)):
        updateExpressions.append("tolerance = :l")
        attributeValues[':l'] = thermostat_data['tolerance']
    if ('mode' in thermostat_data and
            isinstance(thermostat_data['mode'], str) and
            thermostat_data['mode'] in modes):
        updateExpressions.append("#m = :m")
        attributeValues[':m'] = thermostat_data['mode']
        # Necessary because #m is a reserved word for dyanmodb
        expressionAttributeNames['#m'] = 'mode'
    if ('fan' in thermostat_data and
            isinstance(thermostat_data['fan'], str) and
            thermostat_data['fan'] in fan_modes):
        updateExpressions.append("fan = :f")
        attributeValues[':f'] = thermostat_data['fan']

    if len(updateExpressions) < 1:
        raise Exception('Error. Invalid update request.')
    updateExpressionStr = "set " + (",".join(updateExpressions))

    if(expressionAttributeNames):
        state_table().update_item(
            Key={'uuid': uuid},
            UpdateExpression=updateExpressionStr,
            ExpressionAttributeValues=attributeValues,
            ExpressionAttributeNames=expressionAttributeNames)
    else:
        state_table().update_item(
            Key={'uuid': uuid},
            UpdateExpression=updateExpressionStr,
            ExpressionAttributeValues=attributeValues)

    # This method will call the updater lambda
    boto3.client('lambda').invoke(
        FunctionName=os.environ['UPDATER_FUNCTION_NAME'],
        InvocationType='Event')  # Add payload (therm)

    response = {
        "isBase64Encoded": "false",
        "statusCode": 200,
        "body": "{\"message\": \"Thermostat updated\"}"
    }
    return response


def delete_thermostat(uuid):
    # Delete thermostat state
    state_table().delete_item(Key={'uuid': uuid})
    response = {
        "isBase64Encoded": "false",
        "statusCode": 200,
        "body": "{\"message\": \"Thermostat deleted.\"}"
    }
    return response


def lambda_handler(event, context):
    try:
        if event['httpMethod'] == "GET":
            if event['pathParameters'] and 'uuid' in event['pathParameters']:
                return get_thermostat(event['pathParameters']['uuid'])
            else:
                return get_all_thermostats()

        elif event['httpMethod'] == "POST":
            if event['body'] and not event['pathParameters']:
                return create_thermostat(json.loads(event['body']))
            else:
                raise Exception(
                    'Error. HTTP body required for POST to create thermostat.')

        elif event['httpMethod'] == "PUT":
            if (event['body'] and event['pathParameters'] and
                    'uuid' in event['pathParameters']):
                return update_thermostat(event['pathParameters']['uuid'],
                                         json.loads(event['body']))

        elif event['httpMethod'] == "DELETE":
            if event['pathParameters'] and 'uuid' in event['pathParameters']:
                return delete_thermostat(event['pathParameters']['uuid'])
        else:
            raise Exception("Invalid HTTP method")
    except Exception as e:
        response = {
            "isBase64Encoded": "false",
            "statusCode": 400,
            "body": "{\"errorMessage\": \"" + e.args[0] + ".\"}"
        }
        return response
