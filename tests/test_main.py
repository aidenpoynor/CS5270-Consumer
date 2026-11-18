import logging
from argparse import Namespace
from unittest.mock import Mock, call
from consumer.main import run, build_store, build_source
from consumer.models import WidgetRequest, InvalidRequestError
from consumer.request_source import RequestSource, S3RequestSource, SQSRequestSource
from consumer.widget_store import S3WidgetStore, DynamoWidgetStore


def make_request(request_id):
    return WidgetRequest(type="create", request_id=request_id, widget_id="w1", owner="Mary Matthews")


class FakeSource(RequestSource):
    """Returns the scripted items in order, then None forever.
    An Exception in the list is raised instead of returned."""
    def __init__(self, items):
        self.items = list(items)

    def next_request(self):
        item = self.items.pop(0) if self.items else None
        if isinstance(item, Exception):
            raise item
        return item


class TestRun:
    def setup_method(self, method):
        self.processor = Mock()
        self.sleep = Mock()


    def test_all_requests_in_order(self):
        r1, r2 = make_request("r1"), make_request("r2")
        source = FakeSource([r1, r2])

        count = run(source, self.processor, max_idle_polls=1, sleep=self.sleep)

        assert count == 2
        assert self.processor.process.call_args_list == [call(r1), call(r2)]


    def test_idle_limit(self):
        source = FakeSource([])

        count = run(source, self.processor, max_idle_polls=3, sleep=self.sleep)

        assert count == 0
        self.processor.process.assert_not_called()
        assert self.sleep.call_count == 2


    def test_no_sleep_after_successful_request(self):
        source = FakeSource([make_request("r1"), make_request("r2"), make_request("r3")])

        count = run(source, self.processor, max_idle_polls=1, sleep=self.sleep)

        assert count == 3
        self.sleep.assert_not_called()


    def test_idle_counter_reset(self):
        r1, r2 = make_request("r1"), make_request("r2")
        source = FakeSource([None, r1, None, r2])

        count = run(source, self.processor, max_idle_polls=2, sleep=self.sleep)

        assert count == 2
        assert self.processor.process.call_args_list == [call(r1), call(r2)]


    def test_invalid_request(self, caplog):
        r1 = make_request("r1")
        source = FakeSource([InvalidRequestError("bad json"), r1])

        count = run(source, self.processor, max_idle_polls=1, sleep=self.sleep)

        assert count == 1
        self.processor.process.assert_called_once_with(r1)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "Skipping invalid request" in warnings[0].getMessage()
        assert "bad json" in warnings[0].getMessage()


    def test_processing_failure(self, caplog):
        r1, r2 = make_request("r1"), make_request("r2")
        source = FakeSource([r1, r2])
        self.processor.process.side_effect = [RuntimeError("boom"), None]

        count = run(source, self.processor, max_idle_polls=1, sleep=self.sleep)

        assert count == 1
        assert self.processor.process.call_args_list == [call(r1), call(r2)]
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert "Failed to process request r1" in errors[0].getMessage()


    def test_acknowledges_processed_request(self):
        r1 = make_request("r1")
        source = Mock()
        source.next_request.side_effect = [r1, None]

        run(source, self.processor, max_idle_polls=1, sleep=self.sleep)

        source.acknowledge.assert_called_once_with(r1)


    def test_acknowledges_failed_request(self):
        r1 = make_request("r1")
        source = Mock()
        source.next_request.side_effect = [r1, None]
        self.processor.process.side_effect = RuntimeError("boom")

        run(source, self.processor, max_idle_polls=1, sleep=self.sleep)

        source.acknowledge.assert_called_once_with(r1)


class TestBuildSource:
    def test_sqs_source_resolves_queue_name(self):
        args = Namespace(request_bucket=None, request_queue="cs5270-requests")
        session = Mock()
        sqs = session.client.return_value
        sqs.get_queue_url.return_value = {"QueueUrl": "https://sqs.example/cs5270-requests"}

        source = build_source(args, session)

        assert isinstance(source, SQSRequestSource)
        assert source.sqs_client is sqs
        assert source.queue_url == "https://sqs.example/cs5270-requests"
        session.client.assert_called_once_with("sqs")
        sqs.get_queue_url.assert_called_once_with(QueueName="cs5270-requests")


    def test_s3_source(self):
        args = Namespace(request_bucket="b2", request_queue=None)
        session = Mock()

        source = build_source(args, session)

        assert isinstance(source, S3RequestSource)
        assert source.bucket == "b2"
        session.client.assert_called_once_with("s3")


class TestBuildStore:
    def test_s3_storage(self):
        args = Namespace(storage="s3", widget_bucket="b3", table="widgets")
        session = Mock()

        store = build_store(args, session)

        assert isinstance(store, S3WidgetStore)
        assert store.bucket == "b3"
        assert store.s3_client is session.client.return_value
        session.client.assert_called_once_with("s3")


    def test_dynamodb_storage(self):
        args = Namespace(storage="dynamodb", widget_bucket=None, table="my-table")
        session = Mock()

        store = build_store(args, session)

        assert isinstance(store, DynamoWidgetStore)
        session.resource.assert_called_once_with("dynamodb")
        session.resource.return_value.Table.assert_called_once_with("my-table")
        assert store.table is session.resource.return_value.Table.return_value
