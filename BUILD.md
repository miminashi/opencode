# Building opencode

## Prerequisites

- [Bun](https://bun.sh/) runtime (or `npx bun` via Node.js)

## Install dependencies

```bash
cd packages/opencode
bun install
```

## Build

### All platforms (cross-compile)

Builds binaries for all supported platforms (linux, darwin, win32 / x64, arm64 / glibc, musl):

```bash
cd packages/opencode
bun run build
```

### Current platform only

Build a single binary for the current OS and architecture:

```bash
cd packages/opencode
bun run build --single
```

This is the recommended option for local development.

### Build options

| Flag | Description |
|---|---|
| `--single` | Build only for the current platform (OS + arch). Skips musl and baseline variants. |
| `--baseline` | Include the baseline (no-AVX2) variant when used with `--single`. |
| `--skip-install` | Skip `bun install` for platform-specific native dependencies (`@opentui/core`, `@parcel/watcher`). Useful when dependencies are already installed. |

## Output

Build artifacts are placed under `packages/opencode/dist/`:

```
dist/
  opencode-linux-x64/
    bin/
      opencode          # executable binary
    package.json
  opencode-linux-arm64/
    ...
  opencode-darwin-arm64/
    ...
```

With `--single`, only the directory matching the current platform is created.

## Run

```bash
./packages/opencode/dist/opencode-linux-x64/bin/opencode
```

Verify the build:

```bash
./packages/opencode/dist/opencode-linux-x64/bin/opencode --version
```
