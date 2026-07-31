import boto3

def expose(name):
    s3 = boto3.client('s3')
    s3.put_bucket_acl(Bucket=name, ACL='public-read')
