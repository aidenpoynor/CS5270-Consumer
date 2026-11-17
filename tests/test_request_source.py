import dataclasses
from unittest.mock import Mock
import pytest
import boto3
from moto import mock_aws
from consumer.request_source import S3RequestSource, SQSRequestSource
from consumer.models import WidgetRequest, InvalidRequestError
import json

BUCKET = "test-bucket"
QUEUE = "test-queue"

def make_request_body(request_id="r1", widget_id="w1", owner="Mary Matthews", req_type="create"):
    return json.dumps({
        "type": req_type,
        "requestId": request_id,
        "widgetId": widget_id,
        "owner": owner,
        "label": "L",
        "description": "D",
        "otherAttributes": [{"name": "color", "value": "blue"}],
    })


def bucket_keys(s3):
    response = s3.list_objects_v2(Bucket=BUCKET)

    if "Contents" in response:
        objects = response["Contents"]
    else:
        objects = []

    remaining = []
    for obj in objects:
        remaining.append(obj["Key"])
    return remaining


@mock_aws
class TestS3RequestSource:
    def setup_method(self, method):
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket=BUCKET)
        self.source = S3RequestSource(self.s3, BUCKET)


    def test_empty_bucket(self):
        assert self.source.next_request() is None


    def test_bucket_single_item(self):
        self.s3.put_object(Bucket=BUCKET, Key="100", Body=make_request_body())
        result = self.source.next_request()

        assert result == WidgetRequest(
            type="create", request_id="r1", widget_id="w1", owner="Mary Matthews",
            label="L", description="D", other_attributes=[{"name": "color", "value": "blue"}],
        )
        assert "Contents" not in self.s3.list_objects_v2(Bucket=BUCKET)


    def test_bucket_multiple_items(self):
        self.s3.put_object(Bucket=BUCKET, Key="200", Body=make_request_body(request_id="r2"))
        self.s3.put_object(Bucket=BUCKET, Key="100", Body=make_request_body(request_id="r1"))
        result = self.source.next_request()

        assert result.request_id == "r1"

        assert bucket_keys(self.s3) == ["200"]


    def test_multiple_requests(self):
        self.s3.put_object(Bucket=BUCKET, Key="200", Body=make_request_body(request_id="r2"))
        self.s3.put_object(Bucket=BUCKET, Key="100", Body=make_request_body(request_id="r1"))

        result = self.source.next_request()
        assert result.request_id == "r1"

        result = self.source.next_request()
        assert result.request_id == "r2"

        result = self.source.next_request()
        assert result is None


    def test_invalid_request(self):
        self.s3.put_object(Bucket=BUCKET, Key="200", Body="Not JSON")
        with pytest.raises(InvalidRequestError):
            self.source.next_request()

        assert bucket_keys(self.s3) == []


    def test_s3_request_has_no_receipt_handle(self):
        self.s3.put_object(Bucket=BUCKET, Key="100", Body=make_request_body())
        result = self.source.next_request()

        assert result.receipt_handle is None


@mock_aws
class TestSQSRequestSource:
    def setup_method(self, method):
        self.sqs = boto3.client("sqs", region_name="us-east-1")
        self.queue_url = self.sqs.create_queue(QueueName=QUEUE)["QueueUrl"]
        self.source = SQSRequestSource(self.sqs, self.queue_url, wait_seconds=0)


    def queue_total(self):
        """Messages still on the queue, whether visible or in flight (received but not deleted)."""
        attrs = self.sqs.get_queue_attributes(
            QueueUrl=self.queue_url,
            AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
        )["Attributes"]
        return int(attrs["ApproximateNumberOfMessages"]) + int(attrs["ApproximateNumberOfMessagesNotVisible"])


    def test_empty_queue(self):
        assert self.source.next_request() is None


    def test_single_message(self):
        self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=make_request_body())
        result = self.source.next_request()

        assert result.receipt_handle is not None
        assert dataclasses.replace(result, receipt_handle=None) == WidgetRequest(
            type="create", request_id="r1", widget_id="w1", owner="Mary Matthews",
            label="L", description="D", other_attributes=[{"name": "color", "value": "blue"}]
        )


    def test_acknowledge_required(self):
        self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=make_request_body())
        self.source.next_request()

        assert self.queue_total() == 1


    def test_acknowledge_deletes_message(self):
        self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=make_request_body())
        request = self.source.next_request()

        self.source.acknowledge(request)

        assert self.queue_total() == 0


    def test_acknowledge_deletes_specific_message(self):
        self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=make_request_body(request_id="r1"))
        self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=make_request_body(request_id="r2"))
        first = self.source.next_request()
        second = self.source.next_request()

        self.source.acknowledge(first)

        assert self.queue_total() == 1
        assert second.request_id in ("r1", "r2")


    def test_max_batch(self):
        for i in range(12):
            self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=make_request_body(request_id=f"r{i}"))
        spy = Mock(wraps=self.sqs)
        source = SQSRequestSource(spy, self.queue_url, wait_seconds=0)

        for _ in range(10):
            assert source.next_request() is not None
        assert spy.receive_message.call_count == 1

        assert source.next_request() is not None
        assert spy.receive_message.call_count == 2
        assert spy.receive_message.call_args.kwargs["MaxNumberOfMessages"] == 10


    def test_all_messages(self):
        for i in range(12):
            self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=make_request_body(request_id=f"r{i}"))

        received = [self.source.next_request() for _ in range(12)]

        assert sorted(r.request_id for r in received) == sorted(f"r{i}" for i in range(12))
        assert self.source.next_request() is None


    def test_invalid_message_is_deleted_and_raises(self):
        self.sqs.send_message(QueueUrl=self.queue_url, MessageBody="Not JSON")

        with pytest.raises(InvalidRequestError):
            self.source.next_request()

        assert self.queue_total() == 0
