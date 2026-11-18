#!/usr/bin/env bash
# Publish the free public demo to a Hugging Face Docker Space.
#   HF_TOKEN=hf_xxx HF_SPACE=<user>/<space> bash deploy/huggingface/push.sh
# Assembles a clean build context (no raw data, no lakes, no tests) and uploads it; Hugging Face builds the
# image from deploy/huggingface/Dockerfile and serves it on https://<user>-<space>.hf.space.
set -euo pipefail
: "${HF_TOKEN:?set HF_TOKEN (a write token from huggingface.co/settings/tokens)}"
: "${HF_SPACE:?set HF_SPACE as <user>/<space-name>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

cd "$ROOT"
git ls-files -z | grep -zv -E '^(tests/|docs/|deploy/k8s/|deploy/terraform/|ops/|\.github/|web/e2e/)' \
  | xargs -0 -I{} rsync -R "{}" "$OUT/"
cp deploy/huggingface/Dockerfile "$OUT/Dockerfile"
grep -v -x "web" .dockerignore > "$OUT/.dockerignore"
printf "web/node_modules\nweb/dist\n" >> "$OUT/.dockerignore"
cp deploy/huggingface/SPACE_README.md "$OUT/README.md"

python3 - "$OUT" <<'PY'
import os, sys
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
space = os.environ["HF_SPACE"]
api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)
api.upload_folder(folder_path=sys.argv[1], repo_id=space, repo_type="space",
                  commit_message="Deploy UdyamPulse demo", delete_patterns=["*"])
user, name = space.split("/")
print(f"Deployed. Building now: https://huggingface.co/spaces/{space}  ->  https://{user}-{name}.hf.space")
PY
