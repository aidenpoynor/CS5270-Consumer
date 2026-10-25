import argparse

def build_parser():
    parser = argparse.ArgumentParser(description="Widget request consumer", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-s", "--storage", choices=["s3", "dynamodb"], required=True, help="Where to store widgets")
    parser.add_argument("-rb", "--request-bucket", required=True, help="Where requests are received from")
    parser.add_argument("-wb", "--widget-bucket", help="What bucket to store widgets in when using s3 as storage")
    parser.add_argument("-t", "--table", default="widgets", help="What dynamo table to store widgets in when using dynamodb as storage")
    parser.add_argument("-r", "--region", default="us-east-1", help="AWS region")
    parser.add_argument("-p", "--profile", default="default", help="Which profile to use")
    parser.add_argument("--poll-interval", type=int, default=100, help="Main loops wait time between pulling requests in ms")
    parser.add_argument("--max-idle-polls", type=int, default=None, help="Maximum idle pulls main will loop before exiting")
    return parser


def parse_args(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.storage == "s3" and args.widget_bucket is None:
        parser.error("--widget-bucket is required when --storage is s3")

    return args