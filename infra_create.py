import logging
import boto3
import json
import time
from botocore.exceptions import ClientError

BUCKET_NAME='plasz-usecase-6'
LAMBDA_ROLE='plasz_lambda_role'
LAMBDA_NAME='SendMetricsToS3'
LAMBDA_LOGS_POLICY='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
LAMBDA_POLICY_NAME="S3andVolumeAccess"
EVENT_RULE_NAME='everyDay9am'
LAMBDA_TRIGGER_ID='metricsOnceADay'
PACKAGE_FILENAME='lambda_package.zip'

def get_account_id():
    client = boto3.client("sts")
    return client.get_caller_identity()["Account"]

account_id=get_account_id()

def create_bucket(bucket_name):
    try:
        s3_client = boto3.client('s3')
        response = s3_client.create_bucket(Bucket=bucket_name)
        print(response)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def create_lambda_role(role_name, bucket_name):
    
    trusted_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
      ]
    }
    permission_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::%s/*" % bucket_name
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeVolumes",
                "ec2:DescribeSnapshots"
            ],
            "Resource": "*"
        }]
    }
    try:
        iam_client = boto3.client('iam')
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trusted_role_policy),
        )
        print(response)
        response = iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=LAMBDA_LOGS_POLICY
        )
        print(response)
        response = iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=LAMBDA_POLICY_NAME,
            PolicyDocument=json.dumps(permission_role_policy)
        )
        time.sleep(5)
    except ClientError as e:
        logging.error(e)

def set_bucket_permission(bucket_name, role_name):
    bucket_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "AddPerm",
        "Effect": "Allow",
        "Principal": {"AWS":["arn:aws:iam::%s:role/%s" % (account_id, role_name)]},
        "Action": ["s3:PutObject"],
        "Resource": "arn:aws:s3:::%s/*" % bucket_name
    }]
    }
    bucket_policy = json.dumps(bucket_policy)
    print(bucket_policy)
    try:
        s3_client = boto3.client('s3')
        response = s3_client.put_bucket_policy(Bucket=bucket_name, Policy=bucket_policy)
        print(response)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def set_bucket_lifecycle_policy(bucket_name):
    lifecycle_configuration= {
        "Rules": [
        {
            "ID": "MoveToOneZoneOlderThan30d",
            "Status": "Enabled",
            "Filter": {
                "Prefix":"metrics"
            },
            "Transitions": [{
                "Days": 30,
                "StorageClass": "ONEZONE_IA"
            }]
        }]
    }
    try:
        s3_client = boto3.client("s3")
        response = s3_client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration=lifecycle_configuration
        )
        print(response)
    except ClientError as e:
        logging.error(e)

def create_event_rule(event_rule_name):
    try:
        event_client = boto3.client("events")
        response = event_client.put_rule(
            Name=event_rule_name,
            ScheduleExpression="cron(0 9 ? * * *)"
        )
        print(response)
        return response['RuleArn']
    except ClientError as e:
        logging.error(e)

def create_lambda_function(lambda_name,role_name):
    try:
        lambda_client = boto3.client("lambda")
        response = lambda_client.create_function(
            FunctionName=lambda_name,
            Runtime='python3.9',
            Role="arn:aws:iam::%s:role/%s" % (account_id, role_name),
            Handler='lambda_function.lambda_handler',
            Code={
                'ZipFile': open('./'+PACKAGE_FILENAME, 'rb').read()
            },
            Environment={
                'Variables':{
                    'BUCKET_NAME': BUCKET_NAME
                }
            },
            Timeout=10
        )
        print(response)
        return response['FunctionArn']
    except ClientError as e:
        logging.error(e)

def set_lambda_trigger(lambda_name, event_rule_name,lambdaArn, eventArn):
    try:
        event_client = boto3.client("events")
        response = event_client.put_targets(
            Rule=event_rule_name,
            Targets=[{
                'Id': LAMBDA_TRIGGER_ID,
                'Arn': lambdaArn
            }]
        )
        print(response)
        lambda_client = boto3.client("lambda")
        response = lambda_client.add_permission(
            Action='lambda:InvokeFunction',
            FunctionName=lambda_name,
            Principal='events.amazonaws.com',
            SourceArn=eventArn,
            StatementId='eventPermissionToExecute',
        )
        print(response)
    except ClientError as e:
        logging.error(e)

def main():
    create_bucket(BUCKET_NAME)
    create_lambda_role(LAMBDA_ROLE, BUCKET_NAME)
    set_bucket_permission(BUCKET_NAME, LAMBDA_ROLE)
    set_bucket_lifecycle_policy(BUCKET_NAME)
    eventArn=create_event_rule(EVENT_RULE_NAME)
    lambdaArn=create_lambda_function(LAMBDA_NAME, LAMBDA_ROLE)
    set_lambda_trigger(LAMBDA_NAME, EVENT_RULE_NAME, lambdaArn, eventArn)

if __name__ == "__main__":
    main()
