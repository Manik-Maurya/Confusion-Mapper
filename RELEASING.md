# Release process

This file documents how to cut a new ConfusionMapper release. It applies to maintainers only.

## One-time setup (PyPI Trusted Publishing)

1. Create a PyPI account at <https://pypi.org/account/register/> if you do not already have one.
2. Go to <https://pypi.org/manage/account/publishing/> and add a new "pending publisher" with these values:
   - PyPI project name: `confusion-mapper`
   - Owner: `Manik-Maurya`
   - Repository name: `Confusion-Mapper`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. In the GitHub repo go to **Settings -> Environments -> New environment**, name it `pypi`, and (optionally) add a required reviewer so every release needs explicit approval.

This setup means no PyPI API token is ever stored in the repo or in GitHub Secrets. The GitHub Actions runner mints a short-lived OIDC credential each time it publishes.

## Cutting a release

1. Update `version` in `pyproject.toml` and `CITATION.cff`.
2. Add a new top section to `CHANGELOG.md` summarising what changed since the previous release.
3. Commit: `git commit -am "chore: bump version to vX.Y.Z"`.
4. Tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`.
5. Push: `git push origin main --tags`.
6. Create a GitHub Release at <https://github.com/Manik-Maurya/Confusion-Mapper/releases/new>, pick the new tag, paste the CHANGELOG entry as the release notes, and click **Publish release**.
7. The `Publish to PyPI` workflow fires automatically. Watch it in the Actions tab. After it goes green, verify the release at <https://pypi.org/project/confusion-mapper/>.

## Manual release fallback

If Trusted Publishing is misconfigured or you need to publish from a developer machine:

```bash
pip install -e ".[dev]"
pytest tests/ -q              # must be green
rm -rf dist build *.egg-info
python -m build               # produces dist/*.tar.gz and dist/*.whl
twine check dist/*            # validates the metadata PyPI will see
twine upload dist/*           # asks for your PyPI API token
```

Generate the API token at <https://pypi.org/manage/account/token/>. Set its scope to the `confusion-mapper` project (after the first successful upload).

## After a PyPI release

- Confirm `pip install confusion-mapper==X.Y.Z` works in a fresh virtualenv on Python 3.9, 3.10, 3.11, and 3.12.
- Mint a fresh Zenodo archive from the same tag at <https://zenodo.org> by clicking the new release in the GitHub-Zenodo integration. Paste the resulting DOI into `CITATION.cff` and the README badge.
- Add a one-line "see [vX.Y.Z release notes](...)" entry to README's How-to-cite section if the version bump changed the citation.
