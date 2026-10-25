import pytest
import boto3
from moto import mock_aws
from consumer.request_source import S3RequestSource
from consumer.models import WidgetRequest, InvalidRequestError
import json

BUCKET = "test-bucket"

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
class TestRequestSource:
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