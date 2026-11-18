# AWS Widget Consumer

A Python program that reads Widget Requests from either an S3 bucket or an SQS queue and
applies them to widgets stored in either another S3 bucket or a DynamoDB table. It handles
**create**, **update**, and **delete** requests. Several instances can run at once against
the same queue, and the program can be packaged as a Docker image.

## Requirements

- Python 3.10+ (developed on 3.14)
- AWS credentials, either in `~/.aws/credentials` (for AWS Academy, paste the current
  Learner Lab credentials, including `aws_session_token`) or as environment variables
- Java, only to run the instructor-provided `producer.jar` for system testing
- Docker, only to build and run the container image

## Setup

From the project root:

```bash
python -m venv venv
./venv/Scripts/Activate        # Windows (on Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```

## Running the consumer

Run as a module from the project root. Exactly one request source is required: `-rb` (an
S3 bucket) or `-rq` (an SQS queue name).

```powershell
# Read requests from an S3 bucket, store widgets in S3 (Bucket 3)
python -m consumer.main -s s3 -rb <request-bucket> -wb <widget-bucket>

# Read requests from an S3 bucket, store widgets in DynamoDB
python -m consumer.main -s dynamodb -rb <request-bucket>

# Read requests from an SQS queue, store widgets in DynamoDB
python -m consumer.main -s dynamodb -rq <request-queue>
```

| Argument | Description | Default |
|---|---|---|
| `-s`, `--storage` | `s3` or `dynamodb` (required) | |
| `-rb`, `--request-bucket` | S3 bucket to read Widget Requests from (one of `-rb`/`-rq` is required) | |
| `-rq`, `--request-queue` | SQS queue **name** to read Widget Requests from (one of `-rb`/`-rq` is required) | |
| `-wb`, `--widget-bucket` | Bucket to store widgets in (required when `--storage s3`) | |
| `-t`, `--table` | DynamoDB table to store widgets in | `widgets` |
| `-r`, `--region` | AWS region | `us-east-1` |
| `-p`, `--profile` | AWS credentials profile | standard credential chain (env vars, then `default` profile) |
| `--poll-interval` | Milliseconds to wait after an empty poll (SQS long polling already waits up to 20 seconds per call) | `100` |
| `--max-idle-polls` | Stop after this many consecutive empty polls (omit to run until Ctrl+C) | none |

Run `python -m consumer.main --help` for the full list.

### Request sources

**S3 (`-rb`)** lists the bucket one object at a time. Each request is read, deleted from the
bucket, and then processed. Requests are handled in key order.

**SQS (`-rq`)** looks up the queue URL from the queue name, then:

- receives up to 10 messages per call and keeps the extras in a local cache, so each
  receive call covers several requests
- uses long polling (20 seconds) to avoid empty-receive charges and busy loops
- deletes each message from the queue with its receipt handle after the request is processed
- deletes malformed messages immediately, so they are not received again

Because SQS standard queues are at-least-once and unordered, several consumers can run at
once against the same queue, each receiving different messages. An Update or Delete can be
received before the Create it depends on, so it may fail with a "not found" error.

### Request handling

| Type | S3 storage | DynamoDB storage |
|---|---|---|
| `create` | Writes the full widget JSON, replacing any existing object at the key | Writes the widget item, replacing any existing item with that `id` |
| `update` | Reads the stored widget and merges changes (see below), then writes it back | Updates only the supplied fields with a conditional write |
| `delete` | Deletes the object | Deletes the item with a conditional write |

**Update rules:** a field left out of the request (`null` in the JSON) keeps its stored
value. A field sent as an empty string clears it. Attributes are merged by name: a name
that already exists is overwritten, a new name is added, and attributes not mentioned are
kept.

**Owner check:** an update or delete only applies when the owner in the request matches the
stored widget's owner. Otherwise it raises `WidgetNotFoundError`, and nothing is written.

**Failures:** if a request fails, the error and stack trace are logged and the request is
still acknowledged (removed from the source), so it is not retried. Unknown request types
are logged as warnings and skipped.

## Docker

The `Dockerfile` packages the consumer on `python:3.12-slim`. The entry point is
`python -m consumer.main`, and the default arguments read from the SQS queue
`cs5270-requests` and write to the DynamoDB table `widgets`. Arguments passed to
`docker run` replace the defaults.

```bash
# Build the image
docker build -t consumer .

# Run it with credentials from an env file (see below)
docker run --env-file docker.env consumer

# Run in the background, or override the arguments for S3 storage
docker run -d --env-file docker.env consumer
docker run --env-file docker.env consumer -s s3 -rq cs5270-requests -wb <widget-bucket>
```

The `.dockerignore` file keeps tests, sample data, the producer jar, virtual environments,
logs, and any `.env`/`docker.env` file out of the image, so credentials are never baked in.

On ECS/Fargate no env file is needed: the task's IAM role supplies the credentials.

## Logging

The consumer logs to both the console and `logs/consumer.log` (created automatically,
appended to on each run, and excluded from git). Each line has a timestamp, level, the
module that wrote it, and the message. A run records:

- the startup settings
- each request retrieved from the S3 bucket and deleted from it, or retrieved from the SQS
  queue (with message id) and acknowledged after processing
- each batch of messages received from SQS
- each request processed (type, request id, widget id)
- where each widget was written or changed (S3 key or DynamoDB table)
- warnings for skipped requests (unparseable JSON, missing required fields, unknown request
  types, and malformed SQS messages that were deleted)
- errors with stack traces for failed requests, including widgets not found for update or delete
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
  request_source.py  RequestSource interface + S3RequestSource and SQSRequestSource
  widget_store.py    WidgetStore interface + S3WidgetStore, DynamoWidgetStore
  processor.py       Routes each request to the matching store operation
  main.py            Logging setup, wiring, and the polling loop
tests/               One pytest file per module
sample-requests/     Sample Widget Requests provided with the assignment
producer.jar         Instructor-provided Producer for system testing
Dockerfile           Container image definition
.dockerignore        Files excluded from the image
docker.env.example   Example environment file for docker.env
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
  `collections`, `unittest.mock`
