#!/usr/bin/env bash
#
# host_setup.sh — HOST-side (NOT container) one-time setup for the Linux box.
#
# Preps Docker + X11 + VS Code, checks out the newest branch, and opens VS Code
# so you can "Reopen in Container". Run it from inside the cloned repo:
#
#   bash scripts/host_setup.sh
#
# All the fiddly quoting lives here (in a file) so the thing you actually paste
# into the terminal stays quote-free and can't break on smart-quote conversion.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "== nav2gpt host setup =="

# 1. Docker usable without sudo?
if docker run --rm hello-world >/dev/null 2>&1; then
  echo "Docker: ok"
else
  echo "Docker: NOT usable yet. Install it and/or add yourself to the docker group:"
  echo "    curl -fsSL https://get.docker.com | sudo sh"
  echo "    sudo usermod -aG docker \$USER && newgrp docker"
fi

# 2. Let the container draw Gazebo/RViz on your X server
if command -v xhost >/dev/null 2>&1; then
  xhost +local: >/dev/null 2>&1 && echo "X11: local access granted (re-run after reboot if GUIs vanish)"
else
  echo "X11: 'xhost' not found — GUIs may not display (are you on Wayland/headless?)"
fi

# 3. VS Code + Dev Containers extension
if ! command -v code >/dev/null 2>&1; then
  echo "VS Code: not found — installing via snap..."
  sudo snap install code --classic || echo "  Install VS Code manually, then re-run this script."
fi
if command -v code >/dev/null 2>&1; then
  code --install-extension ms-vscode-remote.remote-containers >/dev/null 2>&1 \
    && echo "VS Code: Dev Containers extension ready"
fi

# 4. Make sure all branches are visible, then check out the newest one
git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
git fetch --prune origin
B="$(git for-each-ref --sort=-committerdate --format='%(refname:short)' refs/remotes/origin \
      | grep -vE '^origin$|/HEAD$' | head -n1 | sed 's#^origin/##')"
if [ -n "$B" ]; then
  echo "Checking out newest branch: $B"
  git checkout -B "$B" "origin/$B"
fi

# 5. Open VS Code on this folder
if command -v code >/dev/null 2>&1; then
  code "$REPO_ROOT"
  echo
  echo "----------------------------------------------------------------"
  echo "VS Code opened. Next:"
  echo "  1. Command Palette -> 'Dev Containers: Reopen in Container'"
  echo "  2. Wait for the first build (10-20 min)"
  echo "  3. In the container terminal, once: ollama pull llama3"
  echo "  4. Then run:  bash scripts/ci.sh"
  echo "----------------------------------------------------------------"
fi
