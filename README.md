# nav2gpt — LLM-Powered Robot Navigation with ROS 2 & Nav2

**nav2gpt** lets you speak natural language commands ("Drive to the kitchen") and have a locally-hosted LLM (via Ollama) parse the intent and send navigation goals to a TurtleBot3 simulated in Gazebo using the ROS 2 Nav2 stack.

---

## What's new (dev-setup)

This branch turns the stock project into a working baseline:

- **It navigates.** Fixed the model/costmap mismatch (Gazebo spawns a *burger*
  while Nav2 was set up for a *waffle*), the duplicate `robot_state_publisher`,
  the AMCL initial pose, the map-to-world alignment, and the LLM goal schema — so
  the robot reliably reaches the kitchen, by a direct goal and by voice.
- **Reproducible setup** — a devcontainer, a real `requirements.txt`, and the
  step-by-step instructions below.
- **A build/test/report harness** (`scripts/`): `ci.sh`, pytest smoke tests, a
  main-vs-branch comparison, and a guided integration run, all producing reports.
- **Honest results** — the `goToPose` API server returns Nav2's real outcome
  instead of a hardcoded success.

---

## Architecture Overview

```text
Microphone → Whisper (speech-to-text) → Ollama / LLM (intent parsing)
         → Nav2 goToPose service → TurtleBot3 in Gazebo
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

The `.devcontainer/` folder at the repo root contains the `Dockerfile` and `devcontainer.json` that define the container environment.

### 2. Open in VS Code Dev Container

```bash
code .
```

When VS Code opens, click **"Reopen in Container"** in the notification (bottom-right), or open the Command Palette (`Ctrl+Shift+P`) and run:

```text
Dev Containers: Reopen in Container
```

The first build takes **10–20 minutes** — it installs ROS 2 Humble, Nav2, Gazebo, Ollama, Whisper, and all Python dependencies.

### 3. Ollama Model (automatic)

The container's `postCreateCommand` (`.devcontainer/post_create.sh`) starts the
Ollama server and pulls `llama3` (~4.7 GB) for you on first build — no manual
step needed. It's stored in the persistent `ollama-models` Docker volume and
survives container rebuilds, so it's only ever downloaded once. If the pull
fails (e.g. no network during the build), it prints a warning and you can run
it yourself:

```bash
ollama pull llama3
```

> **Tip:** For faster CPU inference, use a smaller model instead:
> ```bash
> ollama pull llama3.2
> ```
> Then update `nav2gpt_ws/src/ros2ai/ros2ai/nav_gpt.py` where `OllamaLLM` is created:
> ```python
> self.llm = OllamaLLM(model="llama3.2")
> ```

### 4. Build the ROS 2 Workspace

```bash
cd /nav2gpt/nav2gpt_ws
colcon build
source install/setup.bash
```

> **Note:** You may see `UserWarning: Unknown distribution option: 'tests_require'`. That warning is harmless.

> **Running outside the dev container?** The Dev Container installs all Python
> dependencies for you. On a bare ROS 2 Humble machine, install them with:
> ```bash
> pip3 install -r requirements.txt
> ```
> ROS packages themselves (rclpy, Nav2, cv_bridge, …) still come from apt — see
> the `ros-humble-*` list in `.devcontainer/Dockerfile`.

---

## Running the Project

You need **five terminals** open inside the container. In VS Code, open new terminals with `` Ctrl+` `` and the `+` button. (The `scripts/integration_test.sh` harness runs all of these for you and walks you through them.)

### Terminal 1 — Launch Gazebo + TurtleBot3

```bash
source /nav2gpt/nav2gpt_ws/install/setup.bash
ros2 launch ros2ai turtlebot3_navigation.launch.py
```

Wait until Gazebo and RViz fully load before proceeding.

### Terminal 2 — Launch Nav2

```bash
source /nav2gpt/nav2gpt_ws/install/setup.bash
ros2 launch ros2ai navigation2.launch.py
```

> **Note:** `navigation2.launch.py` includes commented-out `gzserver` and `gzclient` launch actions. Keep them commented, because Gazebo is already started in Terminal 1.

### Terminal 3 — Localize (seed AMCL's initial pose)

```bash
source /nav2gpt/nav2gpt_ws/install/setup.bash
./scripts/set_initial_pose.sh          # auto-detects the real spawn pose from Gazebo
```

`set_initial_pose.sh` reads the robot's **actual** spawn pose live from Gazebo (via `scripts/get_spawn_pose.py`) and seeds AMCL with it — no hardcoded guess. You can still override with explicit coordinates (`./scripts/set_initial_pose.sh <x> <y>`) or click **2D Pose Estimate** in RViz.

Required for localization: until AMCL has an initial pose it never publishes the `map → odom` transform, so Nav2 reports `frame [map] does not exist`, navigation goals never resolve, and the API server's service call blocks.

> A `static_transform_publisher map odom` will silence the "frame missing" error, but it *fakes* localization — the costmap ends up offset from reality and the robot paths around walls that aren't there. Seed AMCL instead.

### Terminal 4 — Start the Nav2 API Server

```bash
source /nav2gpt/nav2gpt_ws/install/setup.bash
ros2 run ros2ai nav2_api_server
```

Expected output:

```text
[INFO] [nav2_api_server]: Nav2 API Server is ready
```

### Terminal 5 — Start the LLM Voice Node

```bash
source /nav2gpt/nav2gpt_ws/install/setup.bash
ros2 run ros2ai Nav2Gpt
```

Expected output:

```text
[INFO] [nav_gpt]: connected to goToPose server
Press Enter to start recording...
```

Press **Enter** to begin recording. The node records for a fixed **10 seconds** and then automatically stops. Whisper transcribes the audio, the LLM parses the intent, and the robot navigates to the selected location.

---

## Running the Tests

Tests live in `tests/` (one `test_<feature>.py` per feature). Pure-logic tests
run anywhere; tests needing a live ROS graph skip themselves when ROS isn't
available, so the suite is safe to run on any machine.

```bash
pip3 install -r requirements-dev.txt   # once, installs pytest
./scripts/run_tests.sh                  # runs the suite, writes reports/<branch>_<timestamp>.md
```

`run_tests.sh` runs the pytest suite **and** a functional comparison against
`main` (`compare_with_main.sh`), folding both into one Markdown report. A report
is always written — even if tests fail or pytest/ROS are missing (the
environment is recorded in the report). To publish it back to the branch:

```bash
./scripts/push_report.sh                # commits + pushes the newest report
```

> **Run tests inside the Dev Container.** The harness targets ROS 2 **Humble**,
> which is what the Dev Container provides. Running `colcon`/tests on a host with
> a different ROS distro (e.g. Jazzy) will not work — `build_ws.sh` detects a
> distro mismatch and flags it in the build report.

### Building the workspace (with a captured log)

`scripts/build_ws.sh` runs `colcon build` in `nav2gpt_ws` and tees the full
output into a build report under `reports/`, so build failures are captured and
publishable alongside the test reports. It skips cleanly (writing a SKIP report)
on machines without colcon/ROS.

### Comparing a branch against main

`scripts/compare_with_main.sh` categorizes what a feature branch changes vs
`main` (robot code vs tooling/docs) and runs a per-feature functional check
against both. A tooling-only branch shows zero functional changes — proving
parity with `main`. Each feature branch hones the `feature_check()` function in
that script to probe the specific behavior it adds.

### Watching it run (visual debug)

`scripts/debug_visual.sh` brings the whole stack up on the Linux machine —
Gazebo + Nav2 + API server in the background, the voice node in the foreground —
so you can watch the robot actually move. Ctrl-C tears it all down. Each feature
branch hones the `feature_demo_hint()` in that script to say what to do and what
to watch for.

### Guided integration test

`scripts/integration_test.sh` is an interactive, automated walk-through of the
"Running the Project" steps above: it opens a terminal per stack component,
pauses at each step with instructions (snapping a screenshot when you confirm
it — see below), then asks you to confirm the robot did the right thing and
records a PASS/FAIL integration report. It skips cleanly (writing a SKIP
report) when there's no graphical session or the workspace isn't built. Each
feature branch hones `feature_integration()` with the checkpoints and
pass/fail question for its feature.

It opens real terminal windows via `xterm` (installed in the devcontainer
image). If you're on a container built **before** `xterm`/`imagemagick`/
`xdotool` were added to the Dockerfile, it falls back to running each
component in the background with a log file — rebuild the container
("Dev Containers: Rebuild Container") to get real windows and screenshots.

### Slideshow-ready artifacts

Every guided run captures documentation-quality visuals under
`reports/screenshots/<branch>_<timestamp>/`, embedded in the integration
report: a screenshot of Gazebo/RViz at each confirmed step, a rendered
"branch graph" poster of the project's git history (generated even on a
skipped run — no display needed), and a contact-sheet collage combining a
run's screenshots into one image. All best-effort — missing tools just skip
that capture rather than failing the run.

It also captures the **stdout/stderr of every launched terminal** (Gazebo,
Nav2, localization, API server, voice node) — a capped tail of each is saved
under `reports/logs/<branch>_<timestamp>/` and embedded in the report as
collapsible sections, so component errors travel to GitHub without copy-paste.

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

Room coordinates are currently hardcoded inside the prompt text in `nav2gpt_ws/src/ros2ai/ros2ai/nav_gpt.py`. Edit the room lines inside the prompt string, for example:

```python
remember these the coordinates of the kitchen is x: -4, y: 4, theta: 180

the coordinates of the bedroom is x: 3, y: 4, theta: 0

# Add more rooms in the same style, for example:
# the coordinates of the living room is x: 0, y: -3, theta: 90
```

After editing, rebuild:

```bash
cd /nav2gpt/nav2gpt_ws
colcon build
source install/setup.bash
```

---

## Troubleshooting

**`ollama serve` — address already in use**  
Ollama is already running. Use `ollama list` or `ollama pull` directly.

**`model 'llama3' not found (status code: 404)`**  
The model has not been pulled yet. Run:

```bash
ollama pull llama3
```

**`FP16 is not supported on CPU; using FP32 instead`**  
This warning is harmless. Whisper falls back to FP32 on CPU.

**`colcon build` fails with `option --editable not recognized` or `option --uninstall not recognized`**  
A pip install likely upgraded `setuptools` too far. Fix with:

```bash
pip3 install --user "setuptools<80"
```

**Empty transcription after recording**  
Check microphone access inside the container:

```bash
arecord -l
arecord -d 3 test.wav && aplay test.wav
```

**Map frame missing**  
Add a static transform:

```bash
ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 map odom
```

---

## Project Structure

```text
nav2gpt/
├── .devcontainer/
│   ├── Dockerfile
│   ├── devcontainer.json
│   └── ros_entrypoint.sh
├── README.md
└── nav2gpt_ws/
    └── src/
        ├── ros2ai/
        │   ├── launch/
        │   │   ├── navigation2.launch.py
        │   │   └── turtlebot3_navigation.launch.py
        │   ├── maps/
        │   │   ├── house.pgm
        │   │   └── house.yaml
        │   ├── resource/
        │   ├── ros2ai/
        │   │   ├── __init__.py
        │   │   ├── nav2_api_server.py
        │   │   ├── nav_gpt.py
        │   │   ├── recorded_audio.wav
        │   │   ├── test.mp3
        │   │   ├── test_wispher.py
        │   │   └── whisper_live_test.py
        │   ├── test/
        │   ├── package.xml
        │   ├── setup.cfg
        │   └── setup.py
        └── ros2ai_msgs/
            ├── CMakeLists.txt
            ├── package.xml
            └── srv/
                └── Nav2Gpt.srv
```
