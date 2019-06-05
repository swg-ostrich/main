# Introduction

a fork of swg source, setup and prepared for live servers, large communities, and rapid development. forked from https://github.com/SWG-Source/swg-main

# Initial Setup

### Cloning
 1. `git clone --recurse-submodules -j8 https://github.com/swg-ostrich/ostrich.git`
 2. `cd ostrich`

### Debian
 1. See the [Debian README](/utils/initial-setup/debian/README.md)

# Building
 1. Copy `build.properties` to `local.properties`, update the appropiate settings
 2. run `ant update_configs`
 3. run `ant compile`
 
# Running
 1. Start server by running `./startServer.sh`
