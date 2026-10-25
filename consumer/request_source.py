from abc import ABC, abstractmethod
from consumer.models import parse_request

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
            return parse_request(body)

        return None