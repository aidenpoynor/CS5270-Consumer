import pytest
from consumer.cli import parse_args
from argparse import Namespace

class TestCli:
    def test_correct_s3_args(self):
        args = parse_args(["-s", "s3", "-rb", "b2", "-wb", "b3"])

        assert args == Namespace(
            storage="s3", request_bucket="b2", widget_bucket="b3",
            table="widgets", region="us-east-1", profile="default",
            poll_interval=100, max_idle_polls=None,
        )


    def test_correct_dynamo_args(self):
        args = parse_args(["-s", "dynamodb", "-rb", "b2"])

        assert args == Namespace(
            storage="dynamodb", request_bucket="b2", widget_bucket=None,
            table="widgets", region="us-east-1", profile="default",
            poll_interval=100, max_idle_polls=None,
        )


    def test_default_overrides(self):
        args = parse_args(["-s", "dynamodb", "-rb", "b2", "--table", "t", "-r", "us-west-2", "-p", "cs5260", 
                           "--poll-interval", "250", "--max-idle-polls", "5"])

        assert args == Namespace(
            storage="dynamodb", request_bucket="b2", widget_bucket=None,
            table="t", region="us-west-2", profile="cs5260",
            poll_interval=250, max_idle_polls=5,
        )


    def test_no_widget_bucket(self):
        with pytest.raises(SystemExit):
            parse_args(["-s", "s3", "-rb", "b2"])


    def test_bad_storage_option(self):
        with pytest.raises(SystemExit):
            parse_args(["-s", "mongo", "-rb", "b2"])


    def test_no_storage(self):
        with pytest.raises(SystemExit):
            parse_args(["-rb", "b2"])


    def test_no_request_bucket(self):
        with pytest.raises(SystemExit):
            parse_args(["-s", "s3", "-wb", "b3"])


    def test_no_args(self):
        with pytest.raises(SystemExit):
            parse_args([])


    def test_bad_typing(self):
        with pytest.raises(SystemExit):
            parse_args(["-s", "s3", "-rb", "b2", "-wb", "b3", "--poll-interval", "abc"])