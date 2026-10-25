from moto import mock_aws
import boto3
import json
from consumer.models import WidgetRequest
from consumer.widget_store import S3WidgetStore, DynamoWidgetStore

BUCKET = "test-bucket"
TABLE = "widgets"

def make_request(widget_id="w1", owner="Mary Matthews", label="L", 
                 description="D", other_attributes=[{"name": "color", "value": "blue"}]):
    return WidgetRequest(type="create", request_id="r1", widget_id=widget_id, owner=owner,
                         label=label, description=description, other_attributes=other_attributes)


@mock_aws
class TestS3WidgetStore:
    def setup_method(self, method):
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket=BUCKET)
        self.store = S3WidgetStore(self.s3, BUCKET)

    def read_widget(self, key):
        body = self.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        return json.loads(body)

    def test_create_all_attributes(self):
        self.store.create(make_request())

        assert self.read_widget("widgets/mary-matthews/w1") == {
            "id": "w1", "owner": "Mary Matthews", "label": "L", "description": "D",
            "otherAttributes": [{"name": "color", "value": "blue"}]
        }


    def test_create_no_other_attributes(self):
        self.store.create(make_request(other_attributes=[]))

        assert self.read_widget("widgets/mary-matthews/w1") == {
            "id": "w1", "owner": "Mary Matthews", "label": "L", "description": "D",
            "otherAttributes": []
        }


    def test_create_label_none(self):
        self.store.create(make_request(label=None))

        assert self.read_widget("widgets/mary-matthews/w1") == {
            "id": "w1", "owner": "Mary Matthews", "label": None, "description": "D",
            "otherAttributes": [{"name": "color", "value": "blue"}]
        }


@mock_aws
class TestDynamoWidgetStore:
    def setup_method(self, method):
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        self.table = dynamodb.create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        self.store = DynamoWidgetStore(self.table)

    def read_item(self, widget_id):
        return self.table.get_item(Key={"id": widget_id})["Item"]

    def test_create_all_attributes(self):
        self.store.create(make_request())

        assert self.read_item("w1") == {
            "id": "w1", "owner": "Mary Matthews", "label": "L", "description": "D",
            "color": "blue"
        }


    def test_create_no_other_attributes(self):
        self.store.create(make_request(other_attributes=[]))

        assert self.read_item("w1") == {
            "id": "w1", "owner": "Mary Matthews", "label": "L", "description": "D",
        }


    def test_create_label_none(self):
        self.store.create(make_request(label=None))

        assert self.read_item("w1") == {
            "id": "w1", "owner": "Mary Matthews", "description": "D",
            "color": "blue"
        }