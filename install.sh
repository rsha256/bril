#!/usr/bin/env bash

# install deno
deno --version || curl -fsSL https://deno.land/install.sh | sh

# install the ts bril tools
deno install --allow-all --force --global ts2bril.ts
deno install --allow-all --force --global brili.ts
deno install --allow-all --force --global brilck.ts

# install the python bril tools
# requires flit
# https://flit.pypa.io/en/stable/
pip3 install flit
(cd bril-txt && flit install --symlink)
(cd brench && flit install --symlink)

# install turnt for testing
# https://github.com/cucapra/turnt
pip3 install turnt
