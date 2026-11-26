"""Regression tests for Kleaf's explicit Tango32 distribution boundary.

The shell test uses a fixture tool, not a kernel compiler or real .ko.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "integrate_tango32", ROOT / ".github/scripts/integrate_tango32.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

BUILD_FIXTURE = '''load("//build/bazel_common_rules/dist:dist.bzl", "copy_to_dist_dir")
define_common_kernels(target_configs = {
    "kernel_aarch64": {
        "kmi_symbol_list_strict_mode": True,
        "module_implicit_outs": get_gki_modules_list("arm64"),
    },
})
'''


class Tango32IntegrationTest(unittest.TestCase):
    def test_explicit_module_distribution_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            kernel = Path(tmp) / "kernel"
            source = Path(tmp) / "source"
            source.mkdir()
            drivers = kernel / "common/drivers"
            drivers.mkdir(parents=True)
            for name in ("tango32.c", "tango32.h", "Kconfig", "Makefile"):
                (source / name).write_text("test fixture\n")
            for name in ("Kconfig", "Makefile"):
                (drivers / name).write_text("# existing content\n")
            build = kernel / "common/BUILD.bazel"
            build.write_text(BUILD_FIXTURE)
            MODULE.integrate(kernel, source)
            first = build.read_text()
            MODULE.integrate(kernel, source)
            self.assertEqual(first, build.read_text())
            # Evaluate the relevant Python-compatible Starlark subset to check
            # the actual rule arguments rather than just matching strings.
            rules = {}
            configs = {}
            exec(first, {
                "load": lambda *args: None,
                "get_gki_modules_list": lambda arch: ["existing.ko"],
                "define_common_kernels": lambda **kw: configs.update(kw),
                "copy_to_dist_dir": lambda **kw: rules.update({kw["name"]: kw}),
            })
            self.assertIn("drivers/tango32/tango32.ko",
                          configs["target_configs"]["kernel_aarch64"]["module_implicit_outs"])
            self.assertEqual(rules["tango32_dist"]["data"],
                             [":kernel_aarch64/drivers/tango32/tango32.ko"])
            self.assertTrue(rules["tango32_dist"]["flat"])
            self.assertEqual((drivers / "Kconfig").read_text().count(
                'source "drivers/tango32/Kconfig"'), 1)

    def test_collection_uses_explicit_dist_not_bazel_symlink_search(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/build.yml").read_text())
        step = next(step for job in workflow["jobs"].values()
                    for step in job.get("steps", [])
                    if step.get("name") == "Collect Tango32 module")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            kernel = workspace / "kernel"
            (kernel / "tools").mkdir(parents=True)
            real_out = workspace / "real-bazel-output"
            real_out.mkdir()
            (real_out / "tango32.ko").write_bytes(b"module fixture, not a compiled kernel module\n")
            (kernel / "bazel-bin").symlink_to(real_out, target_is_directory=True)
            # This fixture accepts only the documented explicit dist invocation.
            tool = kernel / "tools/bazel"
            tool.write_text('''#!/usr/bin/env python3
import pathlib, shutil, sys
args = sys.argv[1:]
assert args[:2] == ["run", "--config=fast"], args
assert "--defconfig_fragment=//common:wild_defconfig.fragment" in args, args
assert "//common:tango32_dist" in args, args
assert "--" in args, args
dest = pathlib.Path(next(a.split("=", 1)[1] for a in args if a.startswith("--dist_dir=")))
dest.mkdir(parents=True, exist_ok=True)
shutil.copyfile("bazel-bin/tango32.ko", dest / "tango32.ko")
''')
            tool.chmod(0o755)
            script = step["run"].replace("${{ github.workspace }}", str(workspace))
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                                    cwd=kernel, capture_output=True, text=True,
                                    env={**os.environ, "TMPDIR": tmp})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((workspace / "AnyKernel3/tango32.ko").read_bytes(),
                             (real_out / "tango32.ko").read_bytes())


if __name__ == "__main__":
    unittest.main()
