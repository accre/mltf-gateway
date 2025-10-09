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
    mlflow.log_text(open(__file__, "r").read(), "source.py")
    print("The sum of the array is:", numpy.sum(a))
    print("Exiting now.")
    exit(0)
