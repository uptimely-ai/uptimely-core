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
