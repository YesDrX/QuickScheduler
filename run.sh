#!/usr/bin/bash
export PATH="/data01/dev/softwares/conda_envs/latest/bin/:$PATH"
export PROJECT_DIR=$(realpath $(dirname $0)/)
export PYTHONPATH=$PROJECT_DIR/src

echo "PYTHONPATH=$PYTHONPATH"
echo "cmd: $@"
"$@"