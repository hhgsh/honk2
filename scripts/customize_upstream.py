#!/usr/bin/env python3
"""Customize daeuniverse/openwrt-packages for OpenWrt 25.12.6 x86_64 + latest Honk."""
from pathlib import Path
import re
import shutil
import sys

root = Path(__file__).resolve().parents[1]
wf = root / ".github" / "workflows" / "build-vmlinux-btf.yml"
if not wf.is_file():
    sys.exit(f"ERROR: {wf} not found. Run this script inside your fork of daeuniverse/openwrt-packages.")
src = wf.read_text(encoding="utf-8")

# Keep the upstream dae pin, but resolve Honk dynamically from the Releases API.
version_re = re.compile(
    r'(?P<dae>DAE_VERSION="[^"]+"\s*\n\s*DAE_GIT_TAG="[^"]+")'
    r'\s*\n\s*HONK_VERSION="[^"]+"\s*\n\s*HONK_GIT_TAG="[^"]+"'
)
version_replacement = r'''\g<dae>

# Resolve the newest published Honk release, including prereleases.
# /releases/latest excludes prereleases, so use the releases collection.
HONK_RELEASES="$(curl -fsSL --retry 3 --retry-delay 2 \
  -H 'Accept: application/vnd.github+json' \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  'https://api.github.com/repos/daeuniverse/honk/releases?per_page=100')"
HONK_GIT_TAG="$(jq -er '[.[] | select(.draft == false)] | sort_by(.published_at // .created_at) | last | .tag_name' <<< "$HONK_RELEASES")"

# APK version spelling: 0.1.0-beta.6 -> 0.1.0_beta6.
if [[ "$HONK_GIT_TAG" =~ ^v?([0-9]+\.[0-9]+\.[0-9]+)(-(alpha|beta|rc)\.?([0-9]+))?$ ]]; then
  HONK_VERSION="${BASH_REMATCH[1]}"
  if [[ -n "${BASH_REMATCH[3]:-}" ]]; then
    HONK_VERSION+="_${BASH_REMATCH[3]}${BASH_REMATCH[4]}"
  fi
else
  echo "::error::Unsupported Honk release tag '${HONK_GIT_TAG}'. Expected vX.Y.Z or vX.Y.Z-(alpha|beta|rc).N"
  exit 1
fi
echo "Resolved latest Honk release: ${HONK_GIT_TAG} (APK version ${HONK_VERSION})"
'''
src2, n1 = version_re.subn(version_replacement, src, count=1)
if n1 != 1:
    sys.exit("ERROR: Could not find the upstream DAE/HONK version block; no changes made.")

# Only x86_64 -> x86/64. BTF is generated for the matching target only.
arch_re = re.compile(
    r"(?m)^[ \t]*grep -v '\^#' > /tmp/arches\.txt <<'ARCHES'\r?\n"
    r".*?^[ \t]*ARCHES[ \t]*$",
    re.S,
)
arch_replacement = (
    "grep -v '^#' > /tmp/arches.txt <<'ARCHES'\n"
    "# openwrt_arch|kernel_arch|target/subtarget\n"
    "x86_64|x86_64|x86/64\n"
    "ARCHES"
)
src3, n2 = arch_re.subn(arch_replacement, src2, count=1)
if n2 != 1:
    sys.exit("ERROR: Could not find the upstream architecture matrix block; no changes made.")

# The workflow creates GitHub Releases, so the workflow token must be allowed
# to write repository contents. This is also bounded by repository Actions settings.
perm_re = re.compile(r"(?m)^permissions:\r?\n[ \t]*contents: read[ \t]*$")
src4, n3 = perm_re.subn("permissions:\n  contents: write", src3, count=1)
if n3 != 1:
    sys.exit("ERROR: Could not find the workflow-level contents: read permission; no changes made.")

backup = wf.with_name(wf.name + ".before-customize")
if not backup.exists():
    shutil.copy2(wf, backup)
wf.write_text(src4, encoding="utf-8")
print("Done: latest Honk release + x86_64/x86/64-only matrix + Release write permission.")
print(f"Backup saved to: {backup}")
print("Review with: git diff -- .github/workflows/build-vmlinux-btf.yml")
