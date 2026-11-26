# Tango32 Kleaf collection failure

Failed run: https://github.com/Silvanisle/GKI_FinaSU_SUSFS/actions/runs/45759979062
Source commit: 7daded2112ce2fd19b2585e95bcb07bf53e46e43

## Evidence and cause

The `Build Normal Kernel` step succeeded. Bazel reported `Build completed
successfully, 278 total actions`; Image was copied into AnyKernel3. The final
configuration had CONFIG_KSU=y, CONFIG_KSU_SUSFS=y and 4K pages. The first failed
step was `Collect Tango32 module`, reporting `tango32.ko was not produced by the
GKI build`. That message was an inference from a failed search, not a compiler
diagnostic.

The search used `find bazel-bin /home/runner/out -type f ...`. `bazel-bin` is a
Bazel convenience symlink, which ordinary find does not descend into. In
addition, Tango32 is a `module_implicit_outs` entry: Kleaf does not put it in the
main kernel target's DefaultInfo. Merely building the main target and scanning
its apparent output tree is not a reliable distribution contract.

The manifest selects kernel/build's `main-kernel-build-2023` branch. Its
`define_common_kernels` API accepts `module_implicit_outs`, not an arbitrary
`module_outs` override. Keep that declaration and consume Kleaf's generated
per-output filegroup instead.

## Fix

The integration script adds a small `copy_to_dist_dir` target named
`tango32_dist`, with data `:kernel_aarch64/drivers/tango32/tango32.ko`.
The collection step runs that target with the same fast/fragment settings as
the kernel build and an explicit absolute dist directory, then checks and
installs the resulting module into AnyKernel3. The normal kernel build,
feature flags, component pins and release behavior are unchanged.

## Upstream references

- Selected manifest: https://android.googlesource.com/kernel/manifest/+/refs/heads/common-android14-6.1-2024-08/default.xml
- Macro API and generated module filegroups: https://android.googlesource.com/kernel/build/+/refs/heads/main-kernel-build-2023/kleaf/common_kernels.bzl
- Implicit output semantics, per-output labels and DefaultInfo: https://android.googlesource.com/kernel/build/+/refs/heads/main-kernel-build-2023/kleaf/impl/kernel_build.bzl
- Supported `bazel run ... -- --dist_dir=...` interface: https://android.googlesource.com/platform/build/bazel_common_rules/+/refs/heads/main-kernel-build-2023/dist/dist.bzl
- Tango32 upstream: https://github.com/AmanieuSystems/tango32-module

## Local verification

Run `python3 -m unittest discover -s tests -v` (requires PyYAML).
Tests cover the generated target's arguments, repeated integration, and the
collection shell step with a symlinked Bazel output tree. The shell test uses a
fixture tool and fixture bytes; it does not claim to compile a real module.
Both tests failed before the fix and passed afterward. The patcher was also
exercised twice on the complete upstream common/BUILD.bazel from kernel commit
ab81bbc7927baabd02fec9a034db4be444247f3c, confirming idempotence.
Workflow/composite-action, shell and Python validation passed locally.

A real GitHub Actions build is still required to verify compilation, actual
module distribution, ABI checks and packaging. On-device operation on NX769J
requires separate testing; a successful CI build is not device validation.
