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

`build.json` records the selected specification source and Python source path.
Runs use the saved Python source path unless `--src-path` or the Python run API
explicitly overrides it. Python source paths under the project root are stored
relative to that root. Source directories outside the project remain absolute.
