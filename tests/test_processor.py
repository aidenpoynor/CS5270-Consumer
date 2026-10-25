from unittest.mock import Mock
from consumer.models import WidgetRequest
from consumer.processor import RequestProcessor
from consumer.widget_store import WidgetStore

def make_request(req_type):
    return WidgetRequest(type=req_type, request_id="r1", widget_id="w1", owner="Mary Matthews")


class TestRequestProcessor:
    def setup_method(self, method):
        self.store = Mock(spec=WidgetStore)
        self.processor = RequestProcessor(self.store)


    def test_create(self):
        req = make_request("create")

        self.processor.process(req)

        self.store.create.assert_called_once_with(req)
        self.store.update.assert_not_called()
        self.store.delete.assert_not_called()


    def test_update(self):
        req = make_request("update")

        self.processor.process(req)

        self.store.update.assert_called_once_with(req)
        self.store.create.assert_not_called()
        self.store.delete.assert_not_called()


    def test_delete(self):
        req = make_request("delete")

        self.processor.process(req)

        self.store.delete.assert_called_once_with(req)
        self.store.update.assert_not_called()
        self.store.create.assert_not_called()


    def test_bad_type(self, caplog):
        req = make_request("bad")

        self.processor.process(req)

        self.store.create.assert_not_called()
        self.store.update.assert_not_called()
        self.store.delete.assert_not_called()

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1
        assert "Unknown request type 'bad'" in warnings[0].getMessage()
        assert "r1" in warnings[0].getMessage()