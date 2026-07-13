# Release checklist

- [ ] Version matches `pyproject.toml` and `agentcron/__init__.py`.
- [ ] Changelog and contributor credit are current.
- [ ] `python -m unittest discover -s tests -v` passes.
- [ ] `python -m compileall -q agentcron tests` passes.
- [ ] README quick start and notification example match the CLI/config format.
- [ ] No prompts, logs, webhook URLs, tokens, or local configs are staged.
- [ ] Windows and Linux GitHub Actions jobs pass.
- [ ] Tag and GitHub Release use the same version.
