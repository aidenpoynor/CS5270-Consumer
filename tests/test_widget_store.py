import pytest
from moto import mock_aws
import boto3
import json
from consumer.models import WidgetRequest
from consumer.widget_store import S3WidgetStore, DynamoWidgetStore, WidgetNotFoundError

BUCKET = "test-bucket"
TABLE = "widgets"

def make_request(widget_id="w1", owner="Mary Matthews", label="L",
                 description="D", other_attributes=[{"name": "color", "value": "blue"}]):
    return WidgetRequest(type="create", request_id="r1", widget_id=widget_id, owner=owner,
                         label=label, description=description, other_attributes=other_attributes)


def make_update(widget_id="w1", owner="Mary Matthews", label=None, description=None, other_attributes=None):
    return WidgetRequest(type="update", request_id="r2", widget_id=widget_id, owner=owner,
                         label=label, description=description, other_attributes=other_attributes or [])


def make_delete(widget_id="w1", owner="Mary Matthews"):
    return WidgetRequest(type="delete", request_id="r3", widget_id=widget_id, owner=owner)


RICH_ATTRIBUTES = [{"name": "color", "value": "blue"}, {"name": "width-unit", "value": "cm"}]


@mock_aws
class TestS3WidgetStore:
    def setup_method(self, method):
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket=BUCKET)
        self.store = S3WidgetStore(self.s3, BUCKET)


    def read_widget(self, key="widgets/mary-matthews/w1"):
        body = self.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        return json.loads(body)


    def exists(self, key="widgets/mary-matthews/w1"):
        return "Contents" in self.s3.list_objects_v2(Bucket=BUCKET, Prefix=key)


    def seed_widget(self):
        self.store.create(make_request())


    def seed_rich_widget(self):
        self.store.create(make_request(other_attributes=RICH_ATTRIBUTES))


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


    def test_update_label_only(self):
        self.seed_widget()

        self.store.update(make_update(label="L2"))

        assert self.read_widget() == {
            "id": "w1", "owner": "Mary Matthews", "label": "L2", "description": "D",
            "otherAttributes": [{"name": "color", "value": "blue"}],
        }


    def test_update_merges_attributes(self):
        self.seed_widget()

        self.store.update(make_update(other_attributes=[{"name": "color", "value": "red"},
                                                        {"name": "rating", "value": "5"}]))

        assert sorted(self.read_widget()["otherAttributes"], key=lambda a: a["name"]) == [
            {"name": "color", "value": "red"},
            {"name": "rating", "value": "5"},
        ]


    def test_update_no_changes(self):
        self.seed_rich_widget()
        before = self.read_widget()

        self.store.update(make_update())

        assert self.read_widget() == before


    def test_update_label_and_description(self):
        self.seed_widget()

        self.store.update(make_update(label="L2", description="D2"))

        widget = self.read_widget()
        assert widget["label"] == "L2"
        assert widget["description"] == "D2"


    def test_update_keeps_other_attributes(self):
        self.seed_rich_widget()

        self.store.update(make_update(other_attributes=[{"name": "rating", "value": "5"}]))

        assert sorted(self.read_widget()["otherAttributes"], key=lambda a: a["name"]) == [
            {"name": "color", "value": "blue"},
            {"name": "rating", "value": "5"},
            {"name": "width-unit", "value": "cm"},
        ]


    def test_update_overwrites_attribute(self):
        self.seed_rich_widget()

        self.store.update(make_update(other_attributes=[{"name": "color", "value": "red"}]))

        attrs = self.read_widget()["otherAttributes"]
        assert attrs.count({"name": "color", "value": "red"}) == 1
        assert {"name": "color", "value": "blue"} not in attrs
        assert {"name": "width-unit", "value": "cm"} in attrs


    def test_update_empty_attribute_list(self):
        self.seed_rich_widget()

        self.store.update(make_update(other_attributes=[]))

        assert self.read_widget()["otherAttributes"] == RICH_ATTRIBUTES


    def test_update_missing_widget(self):
        with pytest.raises(WidgetNotFoundError):
            self.store.update(make_update(widget_id="nope", label="x"))

        assert not self.exists("widgets/mary-matthews/nope")


    def test_delete_removes_widget(self):
        self.seed_widget()

        self.store.delete(make_delete())

        assert not self.exists()


    def test_delete_missing_widget(self):
        with pytest.raises(WidgetNotFoundError):
            self.store.delete(make_delete(widget_id="nope"))


    def test_delete_owner_mismatch(self):
        self.seed_widget()

        with pytest.raises(WidgetNotFoundError):
            self.store.delete(make_delete(owner="Someone Else"))

        assert self.exists()


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


    def read_item(self, widget_id="w1"):
        return self.table.get_item(Key={"id": widget_id}).get("Item")


    def seed_widget(self):
        self.store.create(make_request())


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


    def test_update_partial(self):
        self.seed_widget()

        self.store.update(make_update(description="D2"))

        assert self.read_item() == {
            "id": "w1", "owner": "Mary Matthews", "label": "L", "description": "D2", "color": "blue",
        }


    def test_update_merges_attributes(self):
        self.seed_widget()

        self.store.update(make_update(other_attributes=[{"name": "color", "value": "red"},
                                                        {"name": "rating", "value": "5"}]))

        assert self.read_item() == {
            "id": "w1", "owner": "Mary Matthews", "label": "L", "description": "D",
            "color": "red", "rating": "5",
        }


    def test_update_ignores_base_name(self):
        self.seed_widget()

        self.store.update(make_update(other_attributes=[{"name": "owner", "value": "Mallory"}]))

        assert self.read_item()["owner"] == "Mary Matthews"


    def test_update_missing_widget(self):
        with pytest.raises(WidgetNotFoundError):
            self.store.update(make_update(widget_id="nope", label="x"))

        assert self.read_item("nope") is None


    def test_update_owner_mismatch(self):
        self.seed_widget()

        with pytest.raises(WidgetNotFoundError):
            self.store.update(make_update(owner="Someone Else", label="x"))

        assert self.read_item()["label"] == "L"


    def test_empty_update(self):
        self.seed_widget()
        before = self.read_item()

        self.store.update(make_update())

        assert self.read_item() == before


    def test_delete_removes_widget(self):
        self.seed_widget()

        self.store.delete(make_delete())

        assert self.read_item() is None


    def test_delete_missing_widget(self):
        with pytest.raises(WidgetNotFoundError):
            self.store.delete(make_delete(widget_id="nope"))


    def test_delete_owner_mismatch(self):
        self.seed_widget()

        with pytest.raises(WidgetNotFoundError):
            self.store.delete(make_delete(owner="Someone Else"))

        assert self.read_item() is not None
