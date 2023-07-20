import logging
import boto3
import json
from botocore.exceptions import ClientError

BUCKET_NAME="plasz-usecase-6"
LAMBDA_ROLE="plasz_lambda_role"

def get_account_id():
    client = boto3.client("sts")
    return client.get_caller_identity()["Account"]

account_id=get_account_id()

def create_bucket(bucket_name):
    try:
        s3_client = boto3.client('s3')
        s3_client.create_bucket(Bucket=bucket_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def set_bucket_permission(bucket_name, role_name):
    bucket_policy = {
    'Version': '2012-10-17',
    'Statement': [{
        'Sid': 'AddPerm',
        'Effect': 'Allow',
        'Principal': {"AWS":["arn:aws:iam::%s:role/%s" % (account_id, role_name)]},
        'Action': ['s3:PutObject'],
        'Resource': "arn:aws:s3:::%s/*" % bucket_name
    }]
    }
    bucket_policy = json.dumps(bucket_policy)
    print(bucket_policy)
    try:
        s3_client = boto3.client('s3')
        s3_client.put_bucket_policy(Bucket=bucket_name, Policy=bucket_policy)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def create_lambda_role(role_name):
    
    role_policy = {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "",
          "Effect": "Allow",
          "Principal": {
            "Service": "lambda.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }
    try:
        iam_client = boto3.client('iam')
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(role_policy),
        )
        print(response)
    except ClientError as e:
        logging.error(e)

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

def main():
    create_bucket(BUCKET_NAME)
    create_lambda_role(LAMBDA_ROLE)
    set_bucket_permission(BUCKET_NAME, LAMBDA_ROLE)
    set_bucket_lifecycle_policy(BUCKET_NAME)

if __name__ == "__main__":
    main()
