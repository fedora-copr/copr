#! /bin/bash

opt_project=
opt_config=
opt_package_list=
opt_after_build_id=

die() { echo >&2 " !! $*" ; exit 1 ; }

show_help()
{
cat <<EOHELP >&2
Usage: $0 OPTION

Generate large build queue on copr frontend.

Options:
  --config                   Path to copr API config file
  --package-list             Path to file with fedora package list
  --after-build-id           Build ID to append this batch into
  --project                  Name of the project to be created
  --help|-h                  Show this help
EOHELP

test -z "$1" || exit "$1"
}

ARGS=$(getopt -o "h" -l "config:,project:,package-list:,after-build-id:,help" -n "getopt" -- "$@") \
    || show_help 1
eval set -- "$ARGS"

# a ':' after 'a' means -> requires argumetn
# the first ':' means 'silent' mode --> it has significantly different behaviour
# when the ':' is not present
while true; do
    # now the name is in $1 and argument in $2
    case $1 in
    --help|-h)
        show_help 0
        shift
        ;;
    --unused)
        opt=${1##--}
        opt=${opt##-}
        opt=${opt//-/_}
        eval "opt_$opt=:"
        shift
        ;;

    --config|--package-list|--after-build-id|--project)
        opt=${1##--}
        opt=${opt##-}
        opt=${opt//-/_}
        eval "opt_$opt=\$2"
        shift 2
        ;;

    --) # end!
        shift
        break
        ;;

    *)
        echo "programmer mistake ($1)" >&2
        exit 1
        ;;
    esac
done

mandatory_options=( "$opt_config" "$opt_package_list" "$opt_project" )
for mandatory_option in "${mandatory_options[@]}"
do
    test -z "$mandatory_option" && die "Some mandatory option is missing."
done

for file in $opt_config $opt_package_list; do
    test -f "$file" || die "File '$file' not found"
done

set -e
copr=( copr --config "$opt_config" )
"${copr[@]}" create "$opt_project" \
    --chroot fedora-rawhide-x86_64 --chroot fedora-34-x86_64

if test -n "$opt_after_build_id"; then
    opt_after_build_id="--after-build-id $opt_after_build_id"
fi

main_build_id=
set -x
for pkg_name in $(cat "$opt_package_list"); do
    test -z "$main_build_id" && {

        main_build_id=$(
            "${copr[@]}" build-distgit "$opt_project" --nowait \
                --name "$pkg_name" $opt_after_build_id \
            | grep Created\ builds | cut -d' ' -f3)
        echo "Main build ID is '$main_build_id'"
        continue
    }

    set +e
    "${copr[@]}" build-distgit "$opt_project" --nowait \
        --name "$pkg_name" --with-build-id "$main_build_id"
done
