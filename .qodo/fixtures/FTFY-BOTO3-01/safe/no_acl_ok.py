import boto3

def store(name, key):
    s3 = boto3.client('s3')
    s3.put_object(Bucket=name, Key=key, Body=b'x')
