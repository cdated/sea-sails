#!/bin/bash

cd ..
./pants export --py-resolve-format=symlinked_immutable_virtualenv --resolve=python-default
