#!/usr/bin/env bash
#
# post_create.sh — runs once when the devcontainer is first built.
#
# Wires up the shell environment, starts the Ollama server, and pulls the
# llama3 model into the persistent 'ollama-models' volume so it survives
# container rebuilds and never has to be pulled by hand again.

set -uo pipefail

BASHRC="$HOME/.bashrc"

{
  echo "source /opt/ros/$ROS_DISTRO/setup.bash"
  echo "source \${COLCON_WS}/nav2gpt_ws/install/setup.bash 2>/dev/null || true"
  echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp"
  echo "source /usr/share/colcon_cd/function/colcon_cd.sh"
  echo "export _colcon_cd_root=/opt/ros/humble/"
  echo "source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash"
  echo "export TURTLEBOT3_MODEL=burger"
} >> "$BASHRC"

echo "Starting Ollama server..."
pgrep ollama >/dev/null || ollama serve &> /tmp/ollama.log &

echo "Waiting for Ollama server to come up..."
for i in $(seq 1 30); do
  ollama list >/dev/null 2>&1 && break
  sleep 1
done

if ollama list 2>/dev/null | grep -q '^llama3'; then
  echo "Ollama model 'llama3' already present (persistent volume) — skipping pull."
else
  echo "Pulling Ollama model 'llama3' (~4.7 GB, one-time; stored in the persistent volume)..."
  ollama pull llama3 || echo "WARNING: 'ollama pull llama3' failed — run it manually once the server is reachable."
fi

echo "post_create.sh done."
