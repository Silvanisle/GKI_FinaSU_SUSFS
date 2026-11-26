#!/usr/bin/env python3
"""Integrate the pinned Tango32 driver into the Android 14 Kleaf source tree."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def append_once(path: Path, marker: str, addition: str) -> None:
    text = path.read_text()
    if marker not in text:
        path.write_text(text.rstrip() + "\n\n" + addition + "\n")


def integrate(kernel: Path, source: Path) -> None:
    common = kernel / "common"
    driver = common / "drivers" / "tango32"
    driver.mkdir(parents=True, exist_ok=True)
    for filename in ("tango32.c", "tango32.h", "Kconfig", "Makefile"):
        shutil.copy2(source / filename, driver / filename)

    append_once(
        common / "drivers" / "Kconfig",
        'source "drivers/tango32/Kconfig"',
        'source "drivers/tango32/Kconfig"',
    )
    append_once(
        common / "drivers" / "Makefile",
        "obj-$(CONFIG_TANGO32) += tango32/",
        "obj-$(CONFIG_TANGO32) += tango32/",
    )

    build_file = common / "BUILD.bazel"
    text = build_file.read_text()
    anchor = (
        '    "kernel_aarch64": {\n'
        '        "kmi_symbol_list_strict_mode": True,\n'
        '        "module_implicit_outs": get_gki_modules_list("arm64"),\n'
    )
    replacement = (
        '        "module_implicit_outs": get_gki_modules_list("arm64") + '
        '["drivers/tango32/tango32.ko"],\n'
    )
    if replacement.strip() not in text:
        if text.count(anchor) != 1:
            raise RuntimeError(f"Expected exactly one ARM64 Kleaf config in {build_file}")
        text = text.replace(anchor, anchor.replace(
            '"module_implicit_outs": get_gki_modules_list("arm64"),\n',
            replacement,
        ), 1)
        build_file.write_text(text)
    if replacement.strip() not in build_file.read_text():
        raise RuntimeError("Tango32 .ko not declared in Kleaf module_implicit_outs")

    # Implicit outputs are excluded from kernel_aarch64's DefaultInfo. Kleaf
    # creates a per-output filegroup; distribute that explicit label instead of
    # searching the bazel-bin convenience symlink or private output paths.
    append_once(
        build_file,
        '    name = "tango32_dist",',
        'copy_to_dist_dir(\n'
        '    name = "tango32_dist",\n'
        '    data = [":kernel_aarch64/drivers/tango32/tango32.ko"],\n'
        '    flat = True,\n'
        ')',
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--module-source", required=True, type=Path)
    args = parser.parse_args()
    integrate(args.kernel, args.module_source)
    print("Integrated Tango32 Kconfig, Kbuild, and Kleaf module output")


if __name__ == "__main__":
    main()
