from dataclasses import dataclass, field
import json

REQUIRED = ("type", "requestId", "widgetId", "owner")

@dataclass
class WidgetRequest:
    type: str
    request_id: str
    widget_id: str
    owner: str
    label: str | None = None
    description: str | None = None
    other_attributes: list[dict] = field(default_factory=list)


class InvalidRequestError(Exception):
    pass

def parse_request(request_json):
    try:
        request = json.loads(request_json)
    except json.JSONDecodeError as e:
        raise InvalidRequestError(f"Error reading JSON file: {e}") from e

    if not isinstance(request, dict):
        raise InvalidRequestError("Request JSON must be an object")

    missing = []
    for k in REQUIRED:
        if k not in request:
            missing.append(k)

    if missing:
        raise InvalidRequestError(f"Missing required field(s): {missing}")

    return WidgetRequest(request["type"], 
                            request["requestId"], 
                            request["widgetId"], 
                            request["owner"],
                            request.get("label"),
                            request.get("description"),
                            request.get("otherAttributes", []))
