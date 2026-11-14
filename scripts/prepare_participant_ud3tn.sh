#!/usr/bin/env bash
# Prepare patched uD3TN for the IETF 127 CoAP-over-BPv7 participant lab.
# NEVER run this in or over an active Rover/Satellite/Earth source checkout.
# This helper creates a separate source directory, validates the IPN patch,
# and builds the uD3TN POSIX binary. It does not start any DTN processes.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash scripts/prepare_participant_ud3tn.sh [--install|--check]

  --check     Show prerequisites and paths, without cloning or changing files.
  --install   Clone pinned public upstream, verify/apply the patch, and build.

Only run on a new participant VM or an isolated development machine.
Do NOT run over the working Hackathon three-VM deployment.
USAGE
}

MODE="${1:---install}"
case "$MODE" in
  --check|--install) ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH="$REPO_ROOT/patches/ud3tn/ipn-three-component-aap2.patch"
SOURCE_URL='https://github.com/ENTEL-WNG/CoAPoverBP-no-proxy-version.git'
# Verified public upstream main commit; all nine patch input blobs match.
SOURCE_REV='a2fb4311b89b31c30e93a5c1704f78131594e927'
WORKSPACE="${IETF127_WORKSPACE:-$HOME/ietf127-participant}"
SOURCE_DIR="$WORKSPACE/CoAPoverBP-no-proxy-version"
UD3TN_DIR="$SOURCE_DIR/ud3tn"

printf 'Hackathon repository : %s\n' "$REPO_ROOT"
printf 'Original source       : %s\n' "$SOURCE_URL"
printf 'Pinned revision       : %s\n' "$SOURCE_REV"
printf 'New source directory  : %s\n' "$SOURCE_DIR"
printf 'Patch                 : %s\n' "$PATCH"

[[ -f "$PATCH" ]] || { echo 'ERROR: IPN patch missing from Hackathon checkout.' >&2; exit 1; }
for tool in git make gcc; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: missing build tool: $tool (Ubuntu: install git and build-essential)." >&2
    exit 1
  fi
done

if [[ "$MODE" == --check ]]; then
  echo 'CHECK ONLY: prerequisites found; no network access or changes performed.'
  if [[ -e "$SOURCE_DIR" ]]; then
    echo "NOTE: destination already exists; --install will refuse to overwrite: $SOURCE_DIR"
  fi
  exit 0
fi

if [[ -e "$SOURCE_DIR" ]]; then
  echo "ERROR: destination already exists: $SOURCE_DIR" >&2
  echo 'No existing files or running services were changed.' >&2
  echo 'Use a new IETF127_WORKSPACE on an isolated machine if you need another copy.' >&2
  exit 1
fi

mkdir -p "$WORKSPACE"
echo 'Cloning the public no-proxy source into a new directory ...'
git clone "$SOURCE_URL" "$SOURCE_DIR"

cd "$SOURCE_DIR"
# Do not use the moving upstream main branch for experiments.
git checkout --detach "$SOURCE_REV"
ACTUAL_REV="$(git rev-parse HEAD)"
if [[ "$ACTUAL_REV" != "$SOURCE_REV" ]]; then
  echo "ERROR: unexpected original revision: $ACTUAL_REV" >&2
  exit 1
fi

echo 'Checking the nine-file RFC 9758 patch against this source revision ...'
# --index --check requires both staged and working file contents to match
# the expected pre-patch state; it makes no changes.
if ! git apply --index --check "$PATCH"; then
  echo 'ERROR: patch does not apply cleanly to the pinned original source.' >&2
  echo 'Stopped before building. Do not force or partially apply the patch.' >&2
  exit 1
fi

git apply "$PATCH"
echo 'IPN patch applied successfully in the new participant copy.'

# AAP2 Python bindings are tracked in the pinned source tree.
AAP2_PY="$UD3TN_DIR/python-ud3tn-utils/ud3tn_utils/aap2/generated/aap2_pb2.py"
if [[ ! -f "$AAP2_PY" ]]; then
  echo "ERROR: expected generated AAP2 Python bindings missing: $AAP2_PY" >&2
  exit 1
fi

echo 'Building the patched POSIX uD3TN binary ...'
if ! make -C "$UD3TN_DIR" posix -j2; then
  echo 'ERROR: POSIX build failed. Inspect compiler output and install missing build dependencies.' >&2
  echo 'The source was not deleted; no running lab services were modified.' >&2
  exit 1
fi
BIN="$UD3TN_DIR/build/posix/ud3tn"
[[ -x "$BIN" ]] || { echo "ERROR: build finished but binary missing: $BIN" >&2; exit 1; }

cat <<END

Patched uD3TN binary created: $BIN
Source revision           : $SOURCE_REV
IPN patch                 : $PATCH

In your NEW participant VM, from the Hackathon repository root, run:
  export UD3TN_ROOT="$UD3TN_DIR"
  bash scripts/setup_participant_python.sh --live

After that, the three-VM network and contacts still need configuring.
This build step does NOT start uD3TN, connect to Earth, or validate delivery.
END
