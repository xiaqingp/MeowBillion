# Project operating rules

- Use the single existing project directory and website service. Do not create a second development deployment unless requested.
- `ops/` is the sole source for managed systemd units and backup tooling. Make changes here, test and commit them, then install using `sudo python3 ops/manage.py install`.
- Do not edit installed copies directly, bypass the install/check tool, or use containers/other privileged mechanisms to work around missing sudo rights. If administrator access is unavailable, finish and test the installable change and report the exact remaining installation command.
- After installing, require `python3 ops/manage.py check` and the installer's website/real-backup verification before claiming completion. Report repository-only checks separately from checks of installed services.
- Keep private credentials and the real Drive destination outside Git. Do not copy the production database into the repository index.
- Run `.venv/bin/python -m unittest discover -s tests` for relevant code/test changes. The suite also needs Node.js for frontend behavior checks.
