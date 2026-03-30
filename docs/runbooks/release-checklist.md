# Release Checklist - ARIA

## Pre-Release Checklist

### Code Quality
- [ ] All tests pass: `go test ./...`
- [ ] Race detector clean: `go test -race ./...`
- [ ] Vet clean: `go vet ./...`
- [ ] No formatting issues: `gofmt -l .` returns empty
- [ ] Code coverage ≥ 75% (check in CI)

### Documentation
- [ ] CHANGELOG.md updated with all changes
- [ ] Runbook updated if operational changes
- [ ] README updated if needed

### Security
- [ ] No secrets in code (check with `git log` for accidental commits)
- [ ] API keys use environment variables
- [ ] Security scan passed (gosec if configured)

### Testing
- [ ] Manual smoke test on staging
- [ ] Fast path works: `./opencode -p "Hello world"`
- [ ] Deep path works: `./opencode -p "Build a REST API with Go"`

## Release Process

### 1. Version Bump
```bash
# Update version in internal/version/version.go
# Or use goreleaser automatic versioning
git add internal/version/version.go
git commit -m "chore: bump version to vX.Y.Z"
```

### 2. Create Release Branch
```bash
git checkout -b release/vX.Y.Z
git push -u origin release/vX.Y.Z
```

### 3. Run Full CI
```bash
# Wait for CI to pass on release branch
# Check: https://github.com/opencode-ai/opencode/actions
```

### 4. Create Git Tag
```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

### 5. Monitor Release
```bash
# Watch goreleaser action
# Check: https://github.com/opencode-ai/opencode/actions

# Verify artifacts created
ls -la dist/
```

### 6. Verify Installation
```bash
# Homebrew
brew upgrade opencode-ai
opencode --version

# AUR
# Check AUR page for new version

# Manual
wget https://github.com/opencode-ai/opencode/releases/download/vX.Y.Z/...
```

## Post-Release Checklist

- [ ] GitHub release created with changelog
- [ ] Homebrew tap updated (if applicable)
- [ ] AUR package updated (if applicable)
- [ ] Announcement in #releases channel
- [ ] Monitor error rates for 1 hour post-release
- [ ] Verify telemetry/metrics flowing

## Hotfix Process

For critical bugs in production:

1. Create hotfix branch from tag:
   ```bash
   git checkout -b hotfix/vX.Y.Z vX.Y.Z
   ```

2. Apply fix and commit

3. Create hotfix tag:
   ```bash
   git tag -a vX.Y.Z-hotfix1 -m "Hotfix vX.Y.Z-hotfix1"
   git push origin vX.Y.Z-hotfix1
   ```

4. Monitor and verify fix

## Rollback (if needed)
See [rollback-plan.md](./rollback-plan.md)
