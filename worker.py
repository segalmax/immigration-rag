import os
from dotenv import load_dotenv

load_dotenv()

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
AWS_REGION    = os.getenv("AWS_REGION", "us-east-1")


def run():
    raise NotImplementedError


if __name__ == "__main__":
    run()
