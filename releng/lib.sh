#!/bin/bash

function get_all_packages {
    gitroot=$(git rev-parse --show-toplevel)
    echo "$(find $gitroot -maxdepth 2 -path '*spec' -exec dirname {} \;)"
}
