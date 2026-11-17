from abc import ABC, abstractmethod
import logging
from consumer.models import parse_request, InvalidRequestError
from collections import deque

logger = logging.getLogger(__name__)

class RequestSource(ABC):
    @abstractmethod
    def next_request(self):
        """Return the next request, or None if none are available. Raises InvalidRequestError if a request can't be parsed."""


class S3RequestSource(RequestSource):
    def __init__(self, s3_client, bucket):
        self.s3_client = s3_client
        self.bucket = bucket

    def next_request(self):
        response = self.s3_client.list_objects_v2(Bucket=self.bucket, MaxKeys=1)
        if "Contents" in response:
            key = response["Contents"][0]["Key"]
            body = self.s3_client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"Retrieved and deleted request {key} from s3://{self.bucket}")
            try:
                return parse_request(body)
            except InvalidRequestError as e:
                logger.warning(f"Request {key} from s3://{self.bucket} could not be parsed: {e}")
                raise

        return None
    

class SQSRequestSource(RequestSource):
    MAX_BATCH = 10

    def __init__(self, sqs_client, queue_url, wait_seconds=20):
        self.sqs_client = sqs_client
        self.queue_url = queue_url
        self.wait_seconds = wait_seconds
        self.cache = deque()

    def next_request(self):
        if not self.cache:
            self._fill_cache()
        if not self.cache:
            return None
        return self._parse(self.cache.popleft())
    
    def acknowledge(self, request):
        self.sqs_client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=request.receipt_handle)
        logger.info(f"Acknowledged request {request.request_id} from SQS queue {self.queue_url}")
    
    def _fill_cache(self):
        response = self.sqs_client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=self.MAX_BATCH,
            WaitTimeSeconds=self.wait_seconds
        )
        messages = response.get("Messages", [])
        self.cache.extend(messages)
        if messages:
            logger.info(f"Retrieved {len(messages)} messages from SQS queue {self.queue_url}")

    def _parse(self, message):
        try:
            request = parse_request(message["Body"])
        except InvalidRequestError as e:
            self.sqs_client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=message["ReceiptHandle"])
            logger.warning(f"Deleted invalid SQS message {message['MessageId']} from queue {self.queue_url}: {e}")
            raise
        request.receipt_handle = message["ReceiptHandle"]
        logger.info(f"Retrieved request {request.request_id} from SQS message {message['MessageId']}")
        return request