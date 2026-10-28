#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .runtime/bin
curl -fL https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2404-8.0.16.tgz -o .runtime/mongodb.tgz
tar -xzf .runtime/mongodb.tgz -C .runtime/bin --strip-components=2 --wildcards '*/bin/mongod'
.runtime/bin/mongod --version
