#!/usr/bin/env python3

import numpy

# The environment required this version, so it should be there
print("successfully loaded numpy", numpy.__version__)
if __name__ == "__main__":
    print("Hello from myTrainingScript.py!")
    a = numpy.array([1, 2, 3])
    print("Here is a numpy array:", a)
    print("The sum of the array is:", numpy.sum(a))
    print("Exiting now.")
    exit(0)
