# `gaia example`

Print or save CLI walkthrough scripts for shipping v0.5 example packages.

```text
gaia example galileo [--target NAME] [--out PATH] [--force]
gaia example mendel [--target NAME] [--out PATH] [--force]
```

The command does not execute the script or create package files. It reads the
bundled walkthrough, substitutes the target package name, and writes the script
to stdout or to `--out PATH`. Existing output files are preserved unless
`--force` is passed.

Use it when you want a runnable authoring sequence for a known example before
building your own package.
