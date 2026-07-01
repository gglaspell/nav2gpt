# Test report — `feature/dev-setup`

| Field | Value |
|-------|-------|
| Result | **FAIL ❌ (pytest exit 1)** |
| Branch | `feature/dev-setup` |
| Commit | `59abc7f` |
| Run at (UTC) | 20260701T190458Z |
| Host | bragg3d-Precision-7560 |
| ROS | ambient (ROS_DISTRO=jazzy) |
| Python | Python 3.13.9 |
| pytest | Traceback (most recent call last):
pytest not found |
| Platform | `Linux bragg3d-Precision-7560 6.8.0-124-generic #124-Ubuntu SMP PREEMPT_DYNAMIC Tue May 26 13:00:45 UTC 2026 x86_64 x86_64 x86_64 GNU/Linux` |

## pytest output

```
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/pytest/__main__.py", line 9, in <module>
    raise SystemExit(pytest.console_main())
                     ~~~~~~~~~~~~~~~~~~~^^
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/_pytest/config/__init__.py", line 201, in console_main
    code = main()
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/_pytest/config/__init__.py", line 156, in main
    config = _prepareconfig(args, plugins)
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/_pytest/config/__init__.py", line 342, in _prepareconfig
    config = pluginmanager.hook.pytest_cmdline_parse(
        pluginmanager=pluginmanager, args=args
    )
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/pluggy/_hooks.py", line 513, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/pluggy/_callers.py", line 139, in _multicall
    raise exception.with_traceback(exception.__traceback__)
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/pluggy/_callers.py", line 122, in _multicall
    teardown.throw(exception)  # type: ignore[union-attr]
    ~~~~~~~~~~~~~~^^^^^^^^^^^
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/_pytest/helpconfig.py", line 112, in pytest_cmdline_parse
    config = yield
             ^^^^^
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/pluggy/_callers.py", line 103, in _multicall
    res = hook_impl.function(*args)
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/_pytest/config/__init__.py", line 1146, in pytest_cmdline_parse
    self.parse(args)
    ~~~~~~~~~~^^^^^^
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/_pytest/config/__init__.py", line 1527, in parse
    self._preparse(args, addopts=addopts)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/_pytest/config/__init__.py", line 1412, in _preparse
    self.pluginmanager.load_setuptools_entrypoints("pytest11")
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/home/bragg3d/anaconda3/lib/python3.13/site-packages/pluggy/_manager.py", line 421, in load_setuptools_entrypoints
    plugin = ep.load()
  File "/home/bragg3d/anaconda3/lib/python3.13/importlib/metadata/__init__.py", line 179, in load
    module = import_module(match.group('module'))
  File "/home/bragg3d/anaconda3/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1310, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1310, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 1027, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/opt/ros/jazzy/lib/python3.12/site-packages/launch_testing/__init__.py", line 15, in <module>
    from . import tools
  File "/opt/ros/jazzy/lib/python3.12/site-packages/launch_testing/tools/__init__.py", line 18, in <module>
    from .process import launch_process
  File "/opt/ros/jazzy/lib/python3.12/site-packages/launch_testing/tools/process.py", line 17, in <module>
    import launch
  File "/opt/ros/jazzy/lib/python3.12/site-packages/launch/__init__.py", line 17, in <module>
    from . import actions
  File "/opt/ros/jazzy/lib/python3.12/site-packages/launch/actions/__init__.py", line 17, in <module>
    from .declare_launch_argument import DeclareLaunchArgument
  File "/opt/ros/jazzy/lib/python3.12/site-packages/launch/actions/declare_launch_argument.py", line 24, in <module>
    from ..frontend import Entity
  File "/opt/ros/jazzy/lib/python3.12/site-packages/launch/frontend/__init__.py", line 20, in <module>
    from .parser import InvalidFrontendLaunchFileError, Parser
  File "/opt/ros/jazzy/lib/python3.12/site-packages/launch/frontend/parser.py", line 35, in <module>
    from .parse_substitution import parse_if_substitutions
  File "/opt/ros/jazzy/lib/python3.12/site-packages/launch/frontend/parse_substitution.py", line 23, in <module>
    from lark import Lark
ModuleNotFoundError: No module named 'lark'
```
