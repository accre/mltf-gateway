#!/bin/bash

#
# Executed by SLURM. We have to add an extra layer of indirection to
# support using "srun" to execute multiple copies of the same script
#

if [ "${SLURM_NTASKS:-1}" -eq 1 ]; then
  {{command}}
else
  srun --export=ALL {{command}}
fi