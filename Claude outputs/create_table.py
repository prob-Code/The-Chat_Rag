#!/usr/bin/env python3
"""
RagGita — DynamoDB table banao. Ek baar chalana hai, phir kabhi nahi.

    python create_table.py

On-demand billing hai, toh koi capacity planning nahi — jitna use karoge
utna bill. Testing me yeh lagbhag zero hai.
"""
import os
import sys
import boto3
from botocore.exceptions import ClientError

TABLE = os.getenv("DDB_TABLE", "raggita_chat")
REGION = os.getenv("AWS_REGION", "ap-south-1")


def main():
    ddb = boto3.client("dynamodb", region_name=REGION)

    try:
        ddb.describe_table(TableName=TABLE)
        print(f"Table '{TABLE}' already exists in {REGION}. Nothing to do.")
        return 0
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    print(f"Creating '{TABLE}' in {REGION} ...")
    ddb.create_table(
        TableName=TABLE,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.get_waiter("table_exists").wait(TableName=TABLE)
    print("  table ready")

    # Quota rows khud expire ho jaate hain — koi cleanup job nahi chahiye
    try:
        ddb.update_time_to_live(
            TableName=TABLE,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "expiresAt"},
        )
        print("  TTL enabled on 'expiresAt'")
    except ClientError as e:
        print("  TTL not set:", e.response["Error"]["Message"])

    # Galti se delete na ho jaye
    try:
        ddb.update_continuous_backups(
            TableName=TABLE,
            PointInTimeRecoverySpecification={"PointInTimeRecoveryEnabled": True},
        )
        print("  point-in-time recovery enabled")
    except ClientError as e:
        print("  PITR not set:", e.response["Error"]["Message"])

    print("\nDone. Ab Lambda ke execution role pe DynamoDB permission lagana mat bhoolna.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
