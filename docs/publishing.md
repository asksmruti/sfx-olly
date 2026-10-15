# GitHub and PyPI Publishing

Recommended names: GitHub repository **sfx-olly**, PyPI distribution **sfx-olly**,
Python import **sfx_olly**, CLI **sfx-olly**. The repository URL is
`git@github.com:asksmruti/sfx-olly.git`. Confirm PyPI name availability and ownership;
an unused GitHub repository name does not reserve the same name on PyPI.

The recommended sequence is **review -> push to GitHub -> CI -> manual TestPyPI
publication -> install/test -> manual PyPI publication**. A Git push never triggers
an upload. Only an explicitly started publishing workflow can upload packages.

## Before Making the Project Public

1. Confirm you own or have permission to release the code under the [MIT License](../LICENSE).
   Get any required employer approval. A license cannot grant rights you do not have;
   third-party dependencies retain their own licenses.
2. Revoke and rotate API tokens, webhook secrets, ngrok credentials, or publishing tokens
   exposed in messages, logs, screenshots, commits, or shared configuration. Removing
   a value from the current files does not invalidate it.
3. Keep real configuration in local `.env` or an approved secret manager, never in README
   examples, source code, test fixtures, editor settings, or copied SignalFlow programs.
4. Keep both credential fields in `.env.example` blank. Use fictional metrics such as
   `example.project.size`, project `project-demo`, environment `env-test`, and host
   `host-demo`. Replace them only in your local commands/configuration.
5. Review logs and alert payloads for hostnames, customer identifiers, project names,
   network addresses, and business data even if they contain no authentication secrets.

## What Is Excluded

| Local content | Git protection | Distribution protection |
| --- | --- | --- |
| `.env`, environment variants, `.envrc` | Ignored; `.env.example` is the deliberate exception. | Excluded by manifest; only blank `.env.example` is allowed in the source archive. |
| `.pypirc`, `.netrc`, named credential/secret JSON files | Ignored. | Excluded by manifest and rejected by archive checker. |
| Private keys, certificates, PFX/P12 bundles | Ignored by common extensions. | Excluded by manifest and rejected by archive checker. |
| Alert JSONL, `data/`, logs, debug dump | Ignored. | Excluded by manifest and rejected by archive checker. |
| `.vscode/`, virtual environments, caches, build outputs | Ignored. | Local directories excluded; wheel only includes application packages and metadata. |
| Saved `.flow` programs | Ignored because they can contain private filters or logic. | Excluded by manifest and rejected by archive checker. |

Ignore rules are not a complete security boundary. A credential inside an ordinary
Python/Markdown file can still leak. Files with unfamiliar names or extensions need
manual review and an independent secret scanner.

## Prepare the Local Git Repository

If this directory is not a Git repository yet, initialize it yourself when ready:

```bash
git init -b main
```

If a repository already exists, keep its branch/history instead of reinitializing
or deleting anything. The following commands do not print credential values:

```bash
git check-ignore .env .pypirc test.flow .vscode/settings.json
git status --short --ignored
git ls-files -ci --exclude-standard
```

The last command should print nothing: output means files are tracked despite now
matching ignore rules. `.gitignore` only affects untracked files. If necessary, remove
a sensitive file from the index with `git rm --cached -- PATH`, preserving the local
file, then review the staged removal. Do not use a broad destructive reset.

Inspect candidate files locally before staging. Then stage the public files explicitly:

```bash
git add .gitignore .env.example LICENSE MANIFEST.in pyproject.toml requirements.txt
git add README.md docs sfx_olly tests scripts .github
git diff --cached --name-status
git diff --cached --check
```

Review the actual staged diff in your local editor. Do not paste an unreviewed diff
into a support conversation: it could reveal the secret you are checking for.
Do not use `git add -f` on ignored files. Local tests and package checks come next.

After a local commit, an independent history scan is recommended. For example, if
[Gitleaks](https://github.com/gitleaks/gitleaks) is installed:

```bash
gitleaks git . --redact
```

The project does not install Gitleaks. Use a current version and its documentation.
Also enable GitHub push protection and secret scanning where available. These checks
do not replace manual review and may not recognize every Splunk or application token.

## Build and Inspect the Release

Use the intended Python environment from the project directory:

```bash
python -m pip install -e '.[publish]'
python -m unittest discover -s tests -v
python -m build
python -m twine check dist/*
python scripts/check_release.py
```

`python -m build` creates a source archive and a wheel in ignored `dist/`. The source
archive includes public docs, tests, checker, license, and the blank environment template.
The wheel contains application packages and license/metadata, not local config.
`MANIFEST.in` and setuptools configuration protect packaging independently of `.gitignore`.

The checker reads archives without extracting them and reports filenames only. It rejects
common private paths, non-empty example secrets, private keys, and recognized token patterns.
It is a limited release guard, not proof that every possible secret is absent.
Inspect archive file lists and run your independent scanner on staged source/history too.

Remove or move stale build outputs before a later release, then inspect every archive you
intend to upload. Do not accidentally upload older files left in `dist/`.

The GitHub CI workflow runs tests, builds distributions, checks metadata, and runs
the archive guard. It does not deploy, upload artifacts, or need publishing credentials.
Local success does not mean the workflow has already run on GitHub.

## First GitHub Push

Create an empty `asksmruti/sfx-olly` GitHub repository if it does not exist. Do not
initialize it with another README/license when you intend to push this local history.
For a fresh local setup, configure the remote once:

```bash
git remote add origin git@github.com:asksmruti/sfx-olly.git
git remote -v
```

If `origin` is already configured, inspect it rather than adding or overwriting it.
After staging, reviewing, and completing the checks above, create your initial commit
if you have not already done so:

```bash
git commit -m "First commit for signal-fx api"
```

Run the optional Gitleaks history scan if installed, then push when ready:

```bash
git push -u origin main
```

Do not bypass review just because a scanner is unavailable. Never put tokens/passwords
in a remote URL; authenticate using your approved SSH agent. Do not force-push. The
publishing workflow requires `main`; normal CI also checks other pushed branches.

If a secret entered history, stop before pushing, rotate it, and plan history cleanup
with the repository owner. Untracking a file in the latest commit does not erase history.

## PyPI Readiness

The distribution name is `sfx-olly`; the import remains `sfx_olly`. Availability
and ownership of that PyPI name are not assumed. Confirm you can publish it before upload.

- Set the intended release version in `pyproject.toml` and `sfx_olly/__init__.py` together.
- Repository, documentation, and issue URLs in `[project.urls]` point to `asksmruti/sfx-olly`.
   Update them if the repository moves or you choose another project name.
- Check author/contributor attribution and license against approved ownership.
- Keep the Python minimum and dependencies accurate; do not claim untested runtimes.
- Inspect README rendering with `twine check`; links to repository files should be absolute
   GitHub links so the PyPI description can resolve them too.
- Use a fresh virtual environment to smoke-test the built wheel and `sfx-olly --help`.
- Configure the Trusted Publishers and protected environments below. No API token is
  required by the publishing workflow, and no upload is triggered by a push or pull request.

## Configure Trusted Publishing Once

TestPyPI and PyPI are separate services. Create accounts and enable the authentication
they require. Use the GitHub publisher form on each service; for a first release with
no existing project, register a pending publisher. This does not bypass name availability
or project ownership checks.

| Field | TestPyPI publisher | PyPI publisher |
| --- | --- | --- |
| Project/distribution name | `sfx-olly` | `sfx-olly` |
| Publisher | GitHub Actions | GitHub Actions |
| GitHub owner | `asksmruti` | `asksmruti` |
| Repository | `sfx-olly` | `sfx-olly` |
| Workflow filename | `publish.yml` | `publish.yml` |
| Environment | `testpypi` | `pypi` |

In GitHub **Settings -> Environments**, create environments with those exact names.
Limit deployments to `main`. For `pypi`, configure required reviewers where supported
so production publishing pauses for approval. Use an approval setup you can actually
satisfy; preventing self-review requires another eligible maintainer.

The exact repository, workflow filename, and environment must match the publisher
registration. Renaming them requires updating that registration. An environment name
in YAML alone does not configure approval rules: set those explicitly in GitHub.

The publish job obtains a short-lived OIDC credential with `id-token: write`; tests
and builds have read-only repository permissions. Do not add `PYPI_API_TOKEN`, a
password, or your Splunk/ngrok credentials to this workflow.

See the official [Trusted Publisher setup](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
and [GitHub Actions usage](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

## Run a Reviewed Release

1. Review the source, license/ownership, version, and secret checks before pushing.
2. Push to `main`, then wait for the **CI** workflow to pass.
3. Open **Actions -> Publish Python Package -> Run workflow** on `main`.
4. Choose `testpypi`, enter the version from both `pyproject.toml` and
   `sfx_olly/__init__.py`, and start the run. `testpypi` is the default.
5. The workflow checks the branch and version, runs tests, builds fresh distributions,
   checks metadata/private content, and saves a `python-distributions` artifact. The
   publish job uploads exactly that run's validated artifact, without rebuilding it.
6. Inspect the run's commit SHA and artifacts. Verify the TestPyPI package by installing
   it in a separate clean environment and exercising the CLI/library with test data.
   Resolve dependencies from your approved index; avoid mixing untrusted indexes.
7. Start another run choosing `pypi` only after review. Use the same version and source
   commit as the tested run. Each run builds anew; if `main` advanced, retest the changed
   commit on TestPyPI rather than assuming you are publishing the previous artifact.
8. Approve the `pypi` environment deployment if an approval rule is configured, then
   confirm the resulting package and version on PyPI.

To test local artifacts before any external upload, use the local checks above.
Neither the ordinary CI workflow nor opening a pull request invokes publishing.
Starting a manual run is a real upload request, not a dry-run. Choosing production
directly is technically possible if authorized; TestPyPI-first review is the recommended policy.

PyPI release versions cannot be overwritten. Increment the version for later releases,
rebuild, and rerun all checks. Never upload unreviewed files or real configuration.
TestPyPI versions also cannot be overwritten; if a changed candidate needs testing,
choose a new version. No PyPI account, Trusted Publisher, or GitHub environment is
configured automatically by adding these files.
