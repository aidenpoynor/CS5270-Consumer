# AWS Widget Consumer

A Python program that reads Widget Requests from an S3 bucket (Bucket 2) one at a time,
in key order, and stores the resulting widgets in either another S3 bucket (Bucket 3) or
a DynamoDB table. current implementation only handles **create** requests; update and delete requests are
recognized and logged, with their implementation planned for later.

## Requirements

- Python 3.10+ (developed on 3.14)
- AWS credentials configured in `~/.aws/credentials` (for AWS Academy, paste the current
  Learner Lab credentials, including `aws_session_token`)
- Java, only to run the instructor-provided `producer.jar` for system testing

## Setup

From the project root:

```bash
python -m venv venv
./venv/Scripts/Activate
pip install -r requirements.txt
```

## Running the consumer

Run as a module from the project root:

```powershell
# Store widgets in S3 (Bucket 3)
python -m consumer.main -s s3 -rb <request-bucket> -wb <widget-bucket>

# Store widgets in DynamoDB
python -m consumer.main -s dynamodb -rb <request-bucket>
```

| Argument | Description | Default |
|---|---|---|
| `-s`, `--storage` | `s3` or `dynamodb` (required) | |
| `-rb`, `--request-bucket` | Bucket to read Widget Requests from (required) | |
| `-wb`, `--widget-bucket` | Bucket to store widgets in (required when `--storage s3`) | |
| `-t`, `--table` | DynamoDB table to store widgets in | `widgets` |
| `-r`, `--region` | AWS region | `us-east-1` |
| `-p`, `--profile` | AWS credentials profile | `default` |
| `--poll-interval` | Milliseconds to wait after finding no request | `100` |
| `--max-idle-polls` | Stop after this many consecutive empty polls (omit to run until Ctrl+C) | none |

Run `python -m consumer.main --help` for the full list.

### Example system test

```bash
# Terminal 1: generate requests
java -jar producer.jar -rb <request-bucket>

# Terminal 2: consume them, stopping after ~5 seconds with no new requests
python -m consumer.main -s s3 -rb <request-bucket> -wb <widget-bucket> --max-idle-polls 50
```

## Logging

The consumer logs to both the console and `logs/consumer.log` (created automatically,
appended to on each run, and excluded from git). Each line has a timestamp, level, the
module that wrote it, and the message. A run records:

- the startup settings
- each request key retrieved and deleted from the request bucket
- each request processed (type, request id, widget id)
- where each widget was written (S3 key or DynamoDB table)
- warnings for skipped requests (unparseable JSON, missing required fields, unknown
  request types, and update/delete requests not yet implemented)
- errors with stack traces for failed writes
- how many requests were processed when the consumer stops

## Running the tests

```bash
pytest            # run all unit tests
pytest -v         # list each test
```

The tests use [moto](https://github.com/getmoto/moto) to mock S3 and DynamoDB, so they
never touch a real AWS account, and `unittest.mock` for components that don't need AWS.

## Project structure

```
consumer/
  cli.py             Command-line argument parsing
  models.py          WidgetRequest dataclass and JSON parsing/validation
  request_source.py  RequestSource interface + S3RequestSource
  widget_store.py    WidgetStore interface + S3WidgetStore, DynamoWidgetStore
  processor.py       Routes each request to the matching store operation
  main.py            Logging setup, wiring, and the polling loop
tests/               One pytest file per module
sample-requests/     Sample Widget Requests provided with the assignment
producer.jar         Instructor-provided Producer for system testing
```

## Widget storage format

**S3:** the widget is serialized as JSON and stored at `widgets/{owner}/{widget id}`,
where `{owner}` is the owner with spaces replaced by dashes, converted to lower case
(`Mary Matthews` becomes `mary-matthews`).

```json
{"id": "8123f304-...", "owner": "Mary Matthews", "label": "JWJYY",
 "description": "THBRNV...", "otherAttributes": [{"name": "color", "value": "blue"}]}
```

**DynamoDB:** the widget is stored as one item with `id` as the partition key. Each
entry in `otherAttributes` becomes its own top-level attribute instead of a nested list.
Missing optional fields (`label`, `description`) are omitted rather than stored as null.
If another attribute has the same name as a base field (such as `owner`), the base field wins.

```
id, owner, label, description, color, width-unit, rating, ...
```

## Third-party libraries

- [boto3](https://github.com/boto/boto3): AWS SDK for Python
- [pytest](https://pytest.org): test framework and runner
- [moto](https://github.com/getmoto/moto): AWS service mocks for unit tests
- Python standard library: `argparse` (command-line parsing), `logging`, `json`,
  `unittest.mock`
