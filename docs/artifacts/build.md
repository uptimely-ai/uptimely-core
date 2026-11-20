# Build bundle

### Build output

```text
artifacts/
├── build/
│   ├── build.json
│   ├── spec.json
│   └── execution_plan.json
└── explorer.json
```

The Explorer snapshot is separate from the replaceable build bundle and is
atomically replaced only after the managed build succeeds.

`build.json` records the Python source path selected for the build. Runs use
that saved path unless `--src-path` or the Python run API explicitly overrides
it. Paths under the project root are stored relative to that root. Source
directories outside the project remain absolute.
