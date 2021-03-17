#! /bin/bash

our_dir=$(readlink -f "$(dirname "$0")")
export PATH=$PATH:$our_dir

exp_wrapper=bash-interactive-initialized.exp

cmd=(tmux)
first=true

if test $# -eq 0; then
    # default set of tests
    set -- `ls *.sh`
fi


for arg; do
    case $arg in
    *all-in-tmux*|*runtest-production.sh|*upload_authentication.sh)
        continue
        ;;
    esac

    quoted=$(printf %q "$arg")
    if $first; then
        first=false
        cmd+=( new-session -n "$arg" "$exp_wrapper $quoted" )
    else
        cmd+=( ';' new-window -n "$arg" "$exp_wrapper $quoted" )
    fi
done

"${cmd[@]}"
