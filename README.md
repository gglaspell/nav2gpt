# nav2gpt — LLM-Powered Robot Navigation with ROS 2 & Nav2

**nav2gpt** lets you speak natural language commands ("Drive to the kitchen") and have a locally-hosted LLM (via Ollama) parse the intent and send navigation goals to a TurtleBot3 simulated in Gazebo using the ROS 2 Nav2 stack.

---

## Architecture Overview

```
Microphone → Whisper (speech-to-text) → Ollama / LLM (intent parsing)
         → Nav2 /goToPose action server → TurtleBot3 in Gazebo
```

| Component | Tool |
|---|---|
| Robot Simulator | Gazebo (via `ros-humble-turtlebot3-gazebo`) |
| Navigation Stack | Nav2 (`ros-humble-nav2-bringup`) |
| Local LLM Host | Ollama (llama3 or llama3.2) |
| Speech-to-Text | OpenAI Whisper (runs on CPU) |
| LLM ↔ ROS 2 Bridge | LangChain + `langchain-ollama` |
| ROS 2 Distro | Humble Hawksbill |

---

## Prerequisites

- **Ubuntu 22.04** host machine (or compatible)
- **Docker** installed (`docker version` ≥ 24.x)
- **VS Code** with the **Dev Containers** extension (`ms-vscode-remote.remote-containers`)
- A working **microphone** accessible at `/dev/snd`
- ~15 GB free disk space (Docker image + Ollama model)

---

## One-Time Setup (Do This Once)

### 1. Clone the Repository

```bash
git clone https://github.com/gglaspell/nav2gpt.git
cd nav2gpt
```

### 2. Create the Workspace Structure

```bash
mkdir -p nav2gpt_ws/src
cd nav2gpt_ws/src
```

The `.devcontainer/` folder at the repo root contains the `Dockerfile` and `devcontainer.json` that define the container environment.

### 3. Open in VS Code Dev Container

```bash
cd ../..       # back to repo root
code .
```

When VS Code opens, click **"Reopen in Container"** in the notification (bottom-right), or open the Command Palette (`Ctrl+Shift+P`) and run:

```
Dev Containers: Reopen in Container
```

The first build takes **10–20 minutes** — it installs ROS 2 Humble, Nav2, Gazebo, Ollama, Whisper, and all Python dependencies.

### 4. Clone nav2gpt into the Workspace (inside the container)

Once the container is open, run in the VS Code terminal:

```bash
cd /Humble-llm/nav2gpt_ws/src
git clone https://github.com/gglaspell/nav2gpt.git .
```

> **Note:** The `.` at the end clones into the current directory instead of creating a subfolder.

### 5. Pull the Ollama Model

```bash
ollama pull llama3
```

This downloads ~4.7 GB and only needs to be done once. The model is stored in the persistent `ollama-models` Docker volume and survives container rebuilds.

> **Tip:** For faster CPU inference, use a smaller model instead:
> ```bash
> ollama pull llama3.2    # ~2 GB, faster
> ```
> Then update `nav2gpt_ws/src/ros2ai/ros2ai/nav_gpt.py` line 33:
> ```python
> self.llm = OllamaLLM(model="llama3.2")
> ```

### 6. Build the ROS 2 Workspace

```bash
cd /Humble-llm/nav2gpt_ws
colcon build
source install/setup.bash
```

> **Note:** You will see a harmless `UserWarning: Unknown distribution option: 'tests_require'` — this can be ignored.

---

## Running the Project

You need **three terminals** open inside the container. In VS Code, open new terminals with `` Ctrl+` `` and the `+` button.

### Terminal 1 — Launch Gazebo + TurtleBot3 + Nav2

```bash
source /Humble-llm/nav2gpt_ws/install/setup.bash
ros2 launch ros2ai turtlebot3_navigation.launch.py
```

Wait until Gazebo and RViz fully load and Nav2 prints `[lifecycle_manager] Configuring...` messages before proceeding.

### Terminal 2 — Start the Nav2 API Server

```bash
source /Humble-llm/nav2gpt_ws/install/setup.bash
ros2 run ros2ai nav2_api_server
```

Expected output:
```
[INFO] [nav2_api_server]: Nav2 API Server is ready
```

### Terminal 3 — Start the LLM Voice Node

```bash
source /Humble-llm/nav2gpt_ws/install/setup.bash
ros2 run ros2ai Nav2Gpt
```

Expected output:
```
[INFO] [nav_gpt]: connected to goToPose server
Press Enter to start recording...
```

Press **Enter**, speak a command (e.g. *"Drive to the kitchen"*), and press **Enter** again to stop recording. Whisper will transcribe your speech, the LLM will parse the intent, and the robot will navigate to the target location in Gazebo.

---

## Dependency Notes & Known Fixes

During development, the following pip dependency conflicts were encountered and resolved. They are already handled in the Dockerfile, but documented here for reference.

| Package | Problem | Fix |
|---|---|---|
| `transforms3d` (apt 0.3.1) | Uses removed `np.float` and `np.maximum_sctype` | Overridden with pip `>=0.4.2` |
| `scipy` (apt, compiled for NumPy 2.x) | Binary ABI mismatch with NumPy 1.26 | Replaced with pip `>=1.11,<1.14` |
| `torch 2.12+` | Forces NumPy upgrade to 2.x | Pinned to `torch==2.1.2` |
| `opencv-python-headless 4.13` | Requires NumPy ≥ 2 | Pinned to `4.8.1.78` |
| `setuptools 81+` | Breaks `colcon build` (`--editable` flag removed) | Pinned to `<80` |
| `langchain_community.llms.Ollama` | Deprecated in LangChain 0.3.1 | Replaced with `langchain_ollama.OllamaLLM` |

---

## Customizing Navigation Locations

Room coordinates are defined in `nav2gpt_ws/src/ros2ai/ros2ai/nav_gpt.py` as a dictionary in the LLM prompt. Edit these to match your Gazebo map:

```python
locations = {
    "kitchen":  {"x": -4.0, "y":  4.0, "theta": 180},
    "bedroom":  {"x":  3.0, "y":  4.0, "theta":   0},
    "living room": {"x":  0.0, "y": -3.0, "theta":  90},
    # Add more rooms here
}
```

After editing, rebuild:

```bash
cd /Humble-llm/nav2gpt_ws
colcon build
source install/setup.bash
```

---

## Troubleshooting

**`ollama serve` — address already in use**
Ollama is already running (started automatically). Just use `ollama list` or `ollama pull` directly.

**`model 'llama3' not found (status code: 404)`**
The model hasn't been pulled yet. Run `ollama pull llama3`.

**`FP16 is not supported on CPU; using FP32 instead`**
Harmless warning. Whisper falls back to FP32 when no GPU is present. Transcription still works.

**`colcon build` fails with `option --editable not recognized` or `option --uninstall not recognized`**
A pip install upgraded `setuptools` above v80. Fix with:
```bash
pip3 install --user "setuptools<80"
```

**Empty transcription after recording**
Check microphone access inside the container:
```bash
arecord -l    # list recording devices
arecord -d 3 test.wav && aplay test.wav   # record 3s test clip
```

---

## Project Structure

```
nav2gpt/
├── .devcontainer/
│   ├── Dockerfile              # Container image definition
│   ├── devcontainer.json       # VS Code Dev Container config
│   └── ros_entrypoint.sh       # Container entrypoint script
└── nav2gpt_ws/
    └── src/
        ├── ros2ai/             # Main ROS 2 package
        │   ├── ros2ai/
        │   │   ├── nav_gpt.py          # LLM voice node (Whisper + Ollama)
        │   │   └── nav2_api_server.py  # Nav2 goToPose service wrapper
        │   └── launch/
        │       └── turtlebot3_navigation.launch.py
        └── ros2ai_msgs/        # Custom ROS 2 service definitions
            └── srv/
                └── Nav2Gpt.srv
```
