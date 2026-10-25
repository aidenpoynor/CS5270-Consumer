import json
import pytest
from consumer.models import parse_request, InvalidRequestError, WidgetRequest

class TestModels:
    # Ensures full json request parses into a readable object
    def test_full_JSON(self):
        raw = json.dumps({
            "type":"create","requestId":"r1","widgetId":"w1","owner":"Mary Matthews","label":"L","description":"D",
            "otherAttributes":[{"name":"color","value":"blue"}]
        })

        req = parse_request(raw)
        assert req == WidgetRequest(
            type="create", request_id="r1", widget_id="w1", owner="Mary Matthews",
            label="L", description="D", other_attributes=[{"name":"color","value":"blue"}]
        )


    def test_missing_label(self):
        missing_label = json.dumps({
            "type":"create","requestId":"r1","widgetId":"w1","owner":"Mary Matthews","description":"D",
            "otherAttributes":[{"name":"color","value":"blue"}]
        })

        req = parse_request(missing_label)
        assert req == WidgetRequest(
            type="create", request_id="r1", widget_id="w1", owner="Mary Matthews",
            description="D", other_attributes=[{"name":"color","value":"blue"}]
        )


    def test_missing_description(self):
        missing_description = json.dumps({
            "type":"create","requestId":"r1","widgetId":"w1","owner":"Mary Matthews","label":"L",
            "otherAttributes":[{"name":"color","value":"blue"}]
        })

        req = parse_request(missing_description)
        assert req == WidgetRequest(
            type="create", request_id="r1", widget_id="w1", owner="Mary Matthews",
            label="L", other_attributes=[{"name":"color","value":"blue"}]
        )


    def test_missing_other(self):
        missing_other = json.dumps({
            "type":"create","requestId":"r1","widgetId":"w1","owner":"Mary Matthews","label":"L","description":"D"
        })

        req = parse_request(missing_other)
        assert req == WidgetRequest(
            type="create", request_id="r1", widget_id="w1", owner="Mary Matthews",
            label="L", description="D"
        )


    @pytest.mark.parametrize("missing_key", ["type", "requestId", "widgetId", "owner"])
    def test_missing_required(self, missing_key):
        data = {
            "type":"create","requestId":"r1","widgetId":"w1","owner":"Mary Matthews","label":"L","description":"D",
            "otherAttributes":[{"name":"color","value":"blue"}]
        }
        del data[missing_key]

        with pytest.raises(InvalidRequestError, match=missing_key):
            parse_request(json.dumps(data))


    @pytest.mark.parametrize("raw", ["", "Hello World"])
    def test_error_reading_json(self, raw):
        with pytest.raises(InvalidRequestError, match="Error reading JSON"):
            parse_request(raw)


    @pytest.mark.parametrize("raw", ["[]", "5", "null"])
    def test_json_not_object(self, raw):
        with pytest.raises(InvalidRequestError, match="Request JSON must be an object"):
            parse_request(raw)