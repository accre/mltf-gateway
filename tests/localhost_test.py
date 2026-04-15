import unittest
import os
import os.path
import mltf_gateway.scripts.cli as cli
import tempfile

inputs_base = os.path.join(os.path.dirname(__file__), "inputs", "demo-cpu")


class LocalRunTestCase(unittest.TestCase):
    def xtest_full_submit(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["MLFLOW_TRACKING_URI"] = f"file://{td}"

            class TempArg:
                dir = inputs_base

            args = TempArg()
            ret = cli.handle_submit_subcommand(args)
        faaa = ret.wait()
        print(faaa)


if __name__ == '__main__':
    unittest.main()
