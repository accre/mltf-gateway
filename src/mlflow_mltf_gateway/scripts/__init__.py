#
# MLTF CLI - an actual script people can run
#

import argparse

parser = argparse.ArgumentParser(
    prog="mltf", description="Client interface to the MLTF infrastructure"
)
subparser = parser.add_subparsers(dest="sub1")
internal_parser = subparser.add_parser(
    name="internal", description="Testing/debug options, not to be used externally"
)

internal_subparser = internal_parser.add_subparsers(dest="sub2")
internal_payload_parser = internal_subparser.add_parser(
    name="payload",
)

internal_payload_parser.add_argument("run")


# internal_parser.add_subparsers(
#     title = "payload",
#     description = "Generate and execute the payload shell script"
# )
def main():
    args = parser.parse_args()
    import pprint

    pprint.pprint(args)
    if getattr(args, "sub1", None) == "internal":
        if getattr(args, "sub2", None) == "payload":
            if getattr(args, "run", None) == "run":
                print("RUNNING PAYLOAD")
