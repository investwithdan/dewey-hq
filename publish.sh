#!/usr/bin/env bash
# Publish Dewey HQ to GitHub Pages (requires: gh auth login as investwithdan)
set -euo pipefail
cd "$(dirname "$0")"
python3 regenerate.py
OWNER="${GITHUB_OWNER:-investwithdan}"
REPO="${GITHUB_REPO:-dewey-hq}"

if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh is not logged in. Daniel: run 'gh auth login' once (or set GH_TOKEN), then re-run this script."
  exit 1
fi

# Create repo if missing
if ! gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  gh repo create "$OWNER/$REPO" --public --description "Dewey HQ — Grok Bot status dashboard" --source=. --remote=origin --push || true
fi

# Ensure git repo
if [ ! -d .git ]; then
  git init
  git checkout -b main
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$OWNER/$REPO.git"
fi

# Minimal pages content only
cat > .gitignore << 'GI'
.building
__pycache__/
*.pyc
.publish-tmp/
GI

git add index.html gym.html status.json bots.json regenerate.py publish.sh overrides.json
git add -f index.html gym.html
git status
git -c user.email="dewey-hq@local" -c user.name="Dewey HQ" commit -m "Update Dewey HQ status page" || true
git push -u origin main

# Enable GitHub Pages from root of main (may need classic pages API)
gh api -X POST "repos/$OWNER/$REPO/pages" -f build_type=legacy -f source[branch]=main -f source[path]=/ 2>/dev/null \
  || gh api -X PUT "repos/$OWNER/$REPO/pages" -f build_type=legacy -f source[branch]=main -f source[path]=/ 2>/dev/null \
  || echo "Pages enable may need one click in GitHub Settings → Pages → Deploy from branch main / root"

echo "Live URL (after Pages builds ~30s): https://$OWNER.github.io/$REPO/"
