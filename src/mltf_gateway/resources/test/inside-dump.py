#!/usr/bin/env python3

import os
import copy
import json
import sys

ret = { "args": copy.copy(sys.argv),
        "env": {k: v for k,v in os.environ.items()}
      }
ret_str = json.dumps(ret)
sys.stdout.write(ret_str)
