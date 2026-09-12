#!/vendor/bin/sh

# Configuration: action|argument, with insmod, modprobe, enable and setprop.
# Keep processing after a failed load so one optional module cannot prevent
# later attempts or the existing post-fs-data completion handoff. The process
# exit status, not vendor.all.modules.ready, reports aggregate success.

if [ "$#" -ne 1 ]; then
  echo "init.insmod: expected one configuration file" >&2
  exit 1
fi
cfg_file=$1
if [ ! -f "$cfg_file" ] || [ ! -r "$cfg_file" ]; then
  echo "init.insmod: cannot read $cfg_file" >&2
  exit 2
fi

# Module arguments need word splitting, but must not expand filesystem globs.
set -f
failed=0
record_failure() {
  echo "init.insmod: $*" >&2
  failed=1
}

while IFS="|" read -r action arg || [ -n "$action$arg" ]; do
  # Ignore indentation around action names and comment-only lines.
  action=${action#"${action%%[![:space:]]*}"}
  action=${action%"${action##*[![:space:]]}"}
  case "$action" in
    "" | \#*) continue ;;
    "insmod")
      insmod $arg || record_failure "insmod failed: $arg"
      ;;
    "setprop")
      attempts=0
      while ! setprop "$arg" 1; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge 128 ]; then
          record_failure "setprop failed after 128 attempts: $arg"
          break
        fi
      done
      ;;
    "enable")
      echo 1 > "$arg" || record_failure "enable failed: $arg"
      ;;
    "modprobe")
      insmod_arg=$arg
      for partition in system_dlkm vendor; do
        case "$insmod_arg" in
          "-b *" | "-b" | "*" | "")
            if ! arg=$(cat "/${partition}/lib/modules/modules.load"); then
              record_failure "cannot read ${partition} modules.load"
              continue
            fi
            # An empty load list is valid and requires no modprobe invocation.
            [ -n "$arg" ] || continue
            case "$insmod_arg" in
              "-b *" | "-b") arg="-b $arg" ;;
            esac
            ;;
          *) arg=$insmod_arg ;;
        esac
        modprobe -a -d "/${partition}/lib/modules" $arg ||
          record_failure "modprobe failed for ${partition}"
      done
      ;;
    *) record_failure "unknown action: $action" ;;
  esac
done < "$cfg_file"

exit "$failed"
