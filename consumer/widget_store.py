from abc import ABC, abstractmethod
import json
import logging

logger = logging.getLogger(__name__)

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
        logger.info(f"Created widget {request.widget_id} in S3")


    def update(self, request):
        logger.warning(f"Update not implemented yet; skipping request {request.request_id}")


    def delete(self, request):
        logger.warning(f"Delete not implemented yet; skipping request {request.request_id}")



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
        logger.info(f"Created widget {request.widget_id} in DynamoDB")


    def update(self, request):
        logger.warning(f"Update not implemented yet; skipping request {request.request_id}")


    def delete(self, request):
        logger.warning(f"Delete not implemented yet; skipping request {request.request_id}")


def widget_to_s3_key(owner, widget_id):
    owner = owner.replace(" ", "-").lower()
    return f"widgets/{owner}/{widget_id}"