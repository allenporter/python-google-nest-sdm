#!/bin/bash

set -e

python3 setup.py sdist bdist_wheel
twine upload --skip-existing dist/*

