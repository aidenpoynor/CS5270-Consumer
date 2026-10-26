import logging, os, time
import boto3
from consumer.cli import parse_args
from consumer.models import InvalidRequestError
from consumer.request_source import S3RequestSource
from consumer.widget_store import S3WidgetStore, DynamoWidgetStore
from consumer.processor import RequestProcessor

logger = logging.getLogger(__name__)

def main(argv=None):
    args = parse_args(argv)
    setup_logging()
    logger.info(f"Starting consumer: storage={args.storage}, request_bucket={args.request_bucket}, "
                f"widget_bucket={args.widget_bucket}, table={args.table}, region={args.region}, "
                f"profile={args.profile}, poll_interval={args.poll_interval}ms, max_idle_polls={args.max_idle_polls}")
    try:
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
        source = S3RequestSource(session.client("s3"), args.request_bucket)
        store = build_store(args, session)
        processor = RequestProcessor(store)
        run(source, processor, args.poll_interval, args.max_idle_polls)
    except Exception:
        logger.exception("Consumer stopped due to an unexpected error")
        raise


def setup_logging(log_file="logs/consumer.log"):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s", 
                        handlers=[logging.FileHandler(log_file), logging.StreamHandler()])
    for noisy in ("botocore", "boto3", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

def build_store(args, session):
    if args.storage == "s3":
        return S3WidgetStore(session.client("s3"), args.widget_bucket)
    else:
        return DynamoWidgetStore(session.resource("dynamodb").Table(args.table))


def run(source, processor, poll_interval_ms=100, max_idle_polls=None, sleep=time.sleep):
    processed = 0
    idle = 0
    try:
        while True:
            try:
                request = source.next_request()
            except InvalidRequestError as e:
                logger.warning(f"Skipping invalid request: {e}")
                continue

            if request is None:
                idle += 1
                if max_idle_polls is not None and idle >= max_idle_polls:
                    logger.info(f"No requests after {idle} polls. Stopping")
                    break
                sleep(poll_interval_ms / 1000)
                continue

            idle = 0
            try:
                processor.process(request)
                processed += 1
            except Exception:
                logger.exception(f"Failed to process request {request.request_id}")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    logger.info(f"Consumer finished; processed {processed} requests")
    return processed


if __name__ == "__main__":
    main()