#!/usr/bin/env python3

import numpy
import mlflow

# The environment required this version, so it should be there
print("successfully loaded numpy", numpy.__version__)
if __name__ == "__main__":
    print("Hello from myTrainingScript.py!")
    a = numpy.array([1, 2, 3])
    print("Here is a numpy array:", a)
    mlflow.log_param("Example_param", 0.001)
    # mlflow.log_text(open(__file__, "r").read(), "source.py")
    print(f"logging mlflow artifact {__file__}")
    mlflow.log_artifact(__file__)
    print("The sum of the array is:", numpy.sum(a))
    import os, pprint
    print(os.environ)
    print("Exiting now.")
    exit(0)
