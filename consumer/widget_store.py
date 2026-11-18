from abc import ABC, abstractmethod
import json
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

BASE_FIELDS = ("id", "owner", "label", "description")

class WidgetNotFoundError(Exception):
    """Raised when an update or delete targets a widget that doesn't exist for the given owner."""


class WidgetStore(ABC):
    @abstractmethod
    def create(self, request):
        pass
    @abstractmethod
    def update(self, request):
        pass
    @abstractmethod
    def delete(self, request):
        pass


class S3WidgetStore(WidgetStore):
    def __init__(self, s3_client, bucket):
        self.s3_client = s3_client
        self.bucket = bucket


    def create(self, request):
        key = widget_to_s3_key(request.owner, request.widget_id)
        body = json.dumps({"id": request.widget_id, "owner": request.owner, "label": request.label, 
                           "description": request.description, "otherAttributes": request.other_attributes})
        self.s3_client.put_object(Bucket=self.bucket, Key=key, Body=body)
        logger.info(f"Created widget {request.widget_id} at s3://{self.bucket}/{key}")


    def update(self, request):
        key = widget_to_s3_key(request.owner, request.widget_id)
        stored = self._read_widget(key, request)

        attrs = {a["name"]: a["value"] for a in stored.get("otherAttributes", [])}
        for a in request.other_attributes or []:
            attrs[a["name"]] = a["value"]

        updated = {
            "id": stored["id"],
            "owner": stored["owner"],
            "label": request.label if request.label is not None else stored.get("label"),
            "description": request.description if request.description is not None else stored.get("description"),
            "otherAttributes": [{"name": name, "value": value} for name, value in attrs.items()],
        }

        body = json.dumps(updated)
        self.s3_client.put_object(Bucket=self.bucket, Key=key, Body=body)
        logger.info(f"Updated widget {request.widget_id} at s3://{self.bucket}/{key}")


    def delete(self, request):
        key = widget_to_s3_key(request.owner, request.widget_id)
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if _error_code(e) in ("404", "NoSuchKey"):
                raise WidgetNotFoundError(f"Widget {request.widget_id} not found for owner {request.owner}") from e
            raise

        self.s3_client.delete_object(Bucket=self.bucket, Key=key)
        logger.info(f"Deleted widget {request.widget_id} from s3://{self.bucket}/{key}")


    def _read_widget(self, key, request):
        try:
            body = self.s3_client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as e:
            if _error_code(e) in ("404", "NoSuchKey"):
                raise WidgetNotFoundError(f"Widget {request.widget_id} not found for owner {request.owner}") from e
            raise
        return json.loads(body)



class DynamoWidgetStore(WidgetStore):
    def __init__(self, table):
        self.table = table


    def create(self, request):
        widget = {}
        for item in request.other_attributes:
            widget[item["name"]] = item["value"]   

        widget["id"] = request.widget_id
        widget["owner"] = request.owner
        if request.label is not None:
            widget["label"] = request.label
        if request.description is not None:
            widget["description"] = request.description

        self.table.put_item(Item=widget)
        logger.info(f"Created widget {request.widget_id} in DynamoDB table {self.table.name}")


    def update(self, request):
        updates = {}
        if request.label is not None:
            updates["label"] = request.label
        if request.description is not None:
            updates["description"] = request.description
        for attr in request.other_attributes or []:
            if attr["name"] not in BASE_FIELDS:
                updates[attr["name"]] = attr["value"]

        names = {"#id": "id", "#owner": "owner"}
        values = {":owner": request.owner}
        assignments = []
        for i, (name, value) in enumerate(updates.items()):
            names[f"#a{i}"] = name
            values[f":v{i}"] = value
            assignments.append(f"#a{i} = :v{i}")
        if not assignments:
            assignments.append("#owner = :owner")

        try:
            self.table.update_item(
                Key={"id": request.widget_id},
                UpdateExpression="SET " + ", ".join(assignments),
                ConditionExpression="attribute_exists(#id) AND #owner = :owner",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
            )
        except ClientError as e:
            if _error_code(e) == "ConditionalCheckFailedException":
                raise WidgetNotFoundError(f"Widget {request.widget_id} not found for owner {request.owner}") from e
            raise
        logger.info(f"Updated widget {request.widget_id} in DynamoDB table {self.table.name}")


    def delete(self, request):
        try:
            self.table.delete_item(
                Key={"id": request.widget_id},
                ConditionExpression="attribute_exists(#id) AND #owner = :owner",
                ExpressionAttributeNames={"#id": "id", "#owner": "owner"},
                ExpressionAttributeValues={":owner": request.owner},
            )
        except ClientError as e:
            if _error_code(e) == "ConditionalCheckFailedException":
                raise WidgetNotFoundError(f"Widget {request.widget_id} not found for owner {request.owner}") from e
            raise
        logger.info(f"Deleted widget {request.widget_id} from DynamoDB table {self.table.name}")


def widget_to_s3_key(owner, widget_id):
    owner = owner.replace(" ", "-").lower()
    return f"widgets/{owner}/{widget_id}"


def _error_code(error):
    return error.response["Error"]["Code"]
