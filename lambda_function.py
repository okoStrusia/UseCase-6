import boto3
import logging
import json
import dateutil.parser
import os
from botocore.exceptions import ClientError


logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_account_id():
    client = boto3.client("sts")
    return client.get_caller_identity()["Account"]

unattached_disks={"number":0, "size":0}
not_encrypted_disks={"number":0, "size":0}
not_encrypted_snapshots={"number":0, "size":0}

account_id=get_account_id()

def get_metrics():
    try:
        ec2_client = boto3.client("ec2")
        response = ec2_client.describe_volumes()
    except ClientError as e:
        logging.error(e)
    
    for vol in response["Volumes"]:
        if not vol["Attachments"]:
            unattached_disks["number"]+=1
            unattached_disks["size"]+=vol["Size"]
        if not vol["Encrypted"]:
            not_encrypted_disks["number"]+=1
            not_encrypted_disks["size"]+=vol["Size"]
    
    try:
        response = ec2_client.describe_snapshots(
            Filters=[
            {
                'Name': 'encrypted',
                'Values': ['false']
            }],
            OwnerIds=[account_id],
        )
    except ClientError as e:
        logging.error(e)

    for snap in response["Snapshots"]:
        not_encrypted_snapshots["number"]+=1
        not_encrypted_snapshots["size"]+=snap["VolumeSize"]

def push_to_s3(timestamp,bucket_name):
    try:
        s3 = boto3.client("s3")
        logger.info("push to s3: %s %s",timestamp,bucket_name)
        response = s3.put_object(
            Body=json.dumps({"unattached_disks":unattached_disks,
                             "not_encrypted_disks":not_encrypted_disks,
                             "not_encrypted_snapshots":not_encrypted_snapshots}),
            Bucket=bucket_name,
            Key="metrics_%s.json" % timestamp,
        )
        logger.info(response)
    except ClientError as e:
        logger.error(e)

def lambda_handler(event, context):
    logger.info("Starting execution")
    dt = dateutil.parser.parse(event['time'])    
    get_metrics()
    logger.info("Metrics processed")
    bucket_name = os.environ['BUCKET_NAME']
    push_to_s3(dt.timestamp(),bucket_name)
    logger.info("Pushed to S3")
    return {
        'statusCode': 200,
        'body': {}
    }