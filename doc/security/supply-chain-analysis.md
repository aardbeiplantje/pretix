# pretix supply-chain analysis and hardening branch

Branch: `security/supply-chain-hardening`.

## Summary

- Every pinned npm package (327 lockfile entries) and every pinned PyPI artifact in three sets was analysed: the runtime and dev set from `pyproject.toml` (175), the Docker, build, CI, and docs tooling (116, of which 257 unique name@version across both sets), and the vendored and build inputs.
- No compromised artifact was found. All artifacts matched the hashes and integrity values the resolver and lockfile recorded. OSV has no malicious-package (`MAL-*`) record for any pin.
- The real risks are in process and trust, not in the contents of the pinned packages: a publish token exposed to build steps, an unpinned runtime dependency, many packages without provenance, and ownership changes that cannot be verified from the registry alone.
- 10 commits on the branch fix the items that were safe to change without a deployment decision (the 11th is `docker-bake.hcl`). Items that change how the image runs or how releases are published are listed under "Open" and need your call.

## Method

Each artifact was downloaded, verified, and read in memory (no extraction, no execution). Checks, per package:

1. **Integrity.** Wheel/sdist sha256 against the resolver's value; npm tarball sha512 against the lockfile SRI and the registry's `dist.integrity`; wheel `RECORD` hashes for every `*.dist-info`.
2. **Capability scan** of every text file: outbound network, process execution, dynamic exec/eval/pickle, encoded payloads, environment access, credential-file paths, shell/startup persistence, known exfiltration hosts, bidi/zero-width characters, javascript-obfuscator signatures. Severity is tiered so ordinary HTTP and compat code lands at HIGH for review, not CRIT.
3. **Install-time surface.** npm `preinstall`/`install`/`postinstall` and the files they reference; PyPI `setup.py` (sdists), `.pth` files with `import`, `sitecustomize`/`usercustomize`; native binaries in pure wheels; symlinks and unsafe paths.
4. **Diff against the previous release** of the same series. Capabilities or install hooks added in the pinned version, new runtime dependencies, changed repository URL, changed publisher or maintainers, dropped provenance.
5. **Wheel versus sdist** (PyPI): wheel modules absent from the source distribution, and shared modules whose wheel copy adds capabilities.
6. **Provenance.** PyPI per-file attestations (publisher kind, repository, workflow); npm SLSA statement (source repository and commit). Attestation signatures were decoded, not cryptographically re-verified.
7. **Malicious-package and advisory lookup** across all pins via OSV.
8. **Source-versus-artifact** comparison for 15 packages: the published file bytes against the GitHub archive at the release tag or attested commit.

## Coverage

| Set | Artifacts | With provenance |
|---|---|---|
| PyPI runtime and dev (`pyproject.toml`) | 175 | 71 |
| PyPI tooling (Docker, build, CI, docs) | 116 | 44 (combined unique: 97 of 257) |
| npm (`package-lock.json`, dev and optional) | 327 | 97 |

Severity distribution: PyPI runtime 12 CRIT / 47 HIGH / 7 MED / 109 INFO; npm 4 CRIT / 38 HIGH / 41 MED / 168 LOW / 76 INFO. Every CRIT/HIGH category was read at the matched-line level (below); the remaining same-pattern entries were classified by pattern, not one by one. Each is a capability in the context it's used, not evidence of malicious behaviour.

## Results by check

- **Integrity:** 0 hash mismatches (PyPI and npm).
- **Malicious packages:** OSV `MAL-*` records: 0 across 502 main pins and 116 tooling pins. OSV coverage was checked: it does carry records for the September 2025 npm compromise (debug 4.4.2, chalk 5.6.1, ansi-styles 6.2.2, strip-ansi 7.1.1, ansi-regex 6.2.1, wrap-ansi 9.0.1, supports-color 10.2.1, color-convert 3.1.1). The lock pins clean neighbours instead (ansi-regex 6.2.2, ansi-styles 6.2.3, strip-ansi 7.1.2, wrap-ansi 8.1.0, debug 4.4.3, color-convert 2.0.1, supports-color 8.1.1), all dev-only.
- **Advisories (OSV):** pypdf 6.20.1 (14) and oauthlib 3.3.1 (3) in PyPI; minimatch and glob (dev) in npm. The rest of pip-audit and npm audit output is in the scratchpad.
- **Install-time code:** one consumer install hook in the whole lockfile, `@parcel/watcher` (`scripts/build-from-source.js`). It runs `node-gyp rebuild` only when `npm_config_build_from_source=true`, with no network access. Read in full: benign. `fsevents` has only `prepublishOnly`, which doesn't run on install. PyPI sdist builds run `setup.py` at install time; that list is in the report data.
- **Source versus artifact (15 packages):**
  - Byte-identical to the repository at the release tag or attested commit (12): django-phonenumber-field 8.5.0 (19 of 19 shared `.py` files; the sdist-only file is the generated `version.py`), webencodings 0.6.1, vine 5.1.0, pluggy 1.7.0, pytz-deprecation-shim 0.1.0.post0, pretix-plugin-build 1.0.2, requests-toolbelt 1.0.0 (60 of 60, see below), bleach 6.4.0 (55 of 55, including bleach's vendored html5lib patches), ansi-regex 6.2.2, ansi-styles 6.2.3, ms 2.1.3, yocto-queue 0.1.0, token-stream 1.0.0.
  - Identical apart from line endings: color-name 1.1.4 (the published `index.js` is CRLF, 152 lines; identical after normalisation).
  - Not comparable: `@rolldown/pluginutils` 1.0.1 (monorepo, built output; the attested commit exists in `rolldown/plugins`).
- **Ownership transfers:** django-phonenumber-field's old repository URL redirects to the new org, and both tags (8.4.0, 8.5.0) resolve to the same commits, so the history is preserved. Treated as a legitimate transfer.

## Findings and dispositions

### Changed on the branch
- Dependabot npm pointed at a directory that doesn't exist (`.github/dependabot.yml`), so npm update PRs could not be generated from the real manifest.
- Build context excluded `pretix.cfg` and `.secret` only after they were in a layer (`.dockerignore`).
- `/metrics` accepted the empty passphrase when metrics were enabled without one. Confirmed by running the comparison logic; now refused, with regression tests that fail on the old code. Malformed `Authorization` headers now return 401 instead of 500.
- Email image fetch had no timeout (`convert_image_to_cid`).
- pypdf pinned to 6.20.x, which excludes the fixed 6.21.4 (14 advisories: PDF-driven memory and CPU exhaustion, and an arbitrary image-parser path with Pillow).
- oauthlib pinned to 3.3.x, which excludes the fixed 4.0.1 (PKCE timing side-channel; device-code `device_code` not validated). The device-code issue is not reachable: django-oauth-toolkit 2.3 doesn't register that grant.
- pretix-plugin-build was an unpinned runtime dependency of pretix.
- GitHub Actions referenced mutable tags (34 `uses:` lines); now pinned to commit SHAs.
- `prisma-sbom-submit` (which holds the upload token in its step) was installed unpinned; now pinned to 0.0.7.
- GitLab release and test jobs installed twine, build, pretix-plugin-build, check-manifest, wheel, setuptools, pip and uv unpinned; now pinned to the analysed releases.
- Dockerfile upgraded pip and setuptools to latest and installed gunicorn, django-extensions and ipython unpinned as root; now pinned.
- nginx served `/media/tickets/` (ticket PDFs with check-in codes) unauthenticated; now denied, matching `cachedfiles` and `invoices`. No code links to those files directly (verified).

### Reviewed and benign (flagged, read, explained)
- **tqdm 4.70.1** `contrib/telegram.py`: an exfiltration-looking host is the documented Telegram progress feature, sending to the user's own bot token. Present in the previous release too.
- **coverage 7.17.3** `a1_coverage.pth`: `exec` at every Python startup, but it only enables subprocess coverage when `COVERAGE_PROCESS_START` is set. Upstream behaviour (dev dependency).
- **typer 0.29.1**: writes shell completion into `~/.bashrc`/`~/.zshrc` only when the user runs the install command.
- **@vue/compiler-sfc, @parcel/watcher, playwright, vite, ajv, source-map-js, rolldown**: the flagged `net` and `dyn` hits are `LRUCache.fetch`, Redis or template `eval`, `new Function('return 0')` feature detection, napi binding loaders with `ldd --version`, `require("net")` for IPC, and CoffeeScript preprocessing.
- **django-redis 7.0.0**: `client.eval` is Redis Lua. **Pillow**: `ImageMath.eval` is an image function, and `__import__` loads plugins. **Django**: RTL marks in Arabic and Kurdish date formats. **zeep, sentry-sdk**: `profile` is an attribute.
- **six, mt940, xmlschema, aiohttp, requests**: legitimate `urlopen`, `.netrc` reading and compat `exec`. xmlschema's "invisible" hit is a leading BOM.
- **imagesize 2.0.1**: an HTTP reader was added in 2.0.0 (not new in 2.0.1). **jaraco.context 6.1.2**: git and URL helpers, unchanged capability.
- **prisma-sbom-submit 0.0.7**: the token goes only to the `--server` argument, in the upload step, and the collect step (which runs `npm ci`) does not have it. It installs `@cyclonedx/cyclonedx-npm` unpinned at runtime (see Open).
- **pypdf 6.21.4** `filters.py`: runs an external `jbig2dec` from PATH with a copy of the environment. Low risk on a normal server.
- **babel 2.18.0**: `pickle.load` of `babel/global.dat` at import. The 1,084 `.dat` files are byte-identical between sdist and wheel. Cannot be verified by reading; the lock hash is the only control.
- **pygments, execnet, cffi, pytest, pydantic, attrs, typing_extensions, lark, jedi, IPython**: typing and tooling internals, eval/exec as rule names, or documented remote-execution by design.
- **pip and setuptools**: vendored `.exe` launchers (distlib, setuptools cli) and the `distutils-precedence.pth` shipped deliberately.
- **requests-toolbelt 1.0.0**: `adapters/appengine.py` is in the wheel but not in the sdist or the repository at 1.0.0. The file is byte-identical to the 0.10.1 wheel, so it is a stale copy, not an injection.
- **pypdfium2 5.15.2**: its wheel `bindings.py` is regenerated with `--no-load-library --no-system-libsearch` and `search_sys = False`. This is hardening, with no added exec or network code.
- **bleach 6.4.0**: the RECORD for its vendored html5lib lists upstream hashes, while bleach ships patched files (six shim, `wbr`, `formaction` sanitisation, documented in its METADATA). Stale RECORD; the source repository has the same patches.
- **reportlab 5.1.0**: `rl_safe_eval.py` was substantially rewritten (about 100 lines of module filtering). pretix never calls `docExec`, `docEval` or `toColorCanUse`, and it sets `trustedHosts = []`, so the sandbox is not reachable from pretix's code paths as far as I could trace. Worth watching.
- **importlib_metadata 10.2.0** gained `lazy-importer` (first release, trusted publishing from its maintainer's repository). Clean.
- **Maintainer and publisher changes** (31 publisher changes, 24 maintainer-list changes, mostly npm `pug-*`, `token-stream`, `void-elements`, `xml-name-validator` moving between the pugjs maintainers and `qix`, `sindresorhus`, etc.): npm trusted-publishing adoption (human token to GitHub Actions) is positive. The pug family is build-time only (devDependency). Not verifiable from the registry; recorded for review.

### Open (need a decision or a deployment change)
1. **Root in the container. Addressed on the branch (`e09474797`), not yet built.** The application code is root-owned and read-only to the runtime user `pretixuser` (uid 15371, no login shell, no home). sudo is removed, setuid and setgid bits are stripped from the image, and nothing runs as root. nginx listens on 8080, so no capability is needed; operators map `-p 80:8080`. Docker isn't available in the audit environment, so the image build and a running container still need verifying.
2. **PyPI token reachable from build steps.** `.gitlab-ci.yml:21` writes `$PYPIRC` to `~/.pypirc` in `before_script`; later `npm ci`, `setup.py`, `python -m build` and `python -m pretix migrate` can read it. Pinning the tools doesn't fix this. Fix: PyPI trusted publishing (OIDC), or a build job without the token and a publish job that only receives `dist/`.
3. **Login throttling is off in the default container, and a spoofable header is taken as the client IP.** `helpers/ratelimit.py` does nothing without Redis; the Unix-socket gunicorn gives an empty `REMOTE_ADDR`; and `helpers/http.py:43` takes the leftmost `X-Forwarded-For` entry, which nginx leaves client-controlled (`nginx.conf:88`, `$proxy_add_x_forwarded_for`). The right fix depends on the topology: behind a CDN the rightmost entry is the CDN, so it must be a configured number of trusted hops.
4. **pdf.js upgraded to 6.5.438 (`75ea2f09b`), not yet verified in a browser.** The layout editor previously ran 3.0.279, affected by CVE-2024-4367. The module loads on demand, and WebAssembly is off for the editor (`useWasm: false`). Every WebAssembly path in the build is gated by that setting, and the editor works with WebAssembly removed from the global scope (checked in Node). JBIG2 and JPEG 2000 use their JavaScript fallbacks, and ICC profiles fall back to the device colour space. The cost is the browser floor. Unlike 4.10.38, 6.5.438 calls these built-ins unconditionally, so engines without them cannot open documents in the editor: `Map.prototype.getOrInsertComputed` (used by the operator-list cache and the shortcut manager), Iterator helpers, `Promise.try`, `Promise.withResolvers`, `Uint8Array.prototype.toHex`, `Math.sumPrecise`, the Set methods, and the Array `toSorted`/`toReversed`/`toSpliced`/`with` methods. `Float16Array` is feature-detected and optional. The commit message of `75ea2f09b` does not list `getOrInsertComputed`. Firefox ESR 128 is dropped. Whether current browser releases provide all of these was not checked here, so test the editor in every browser you support before merging. The alternatives are polyfills for these built-ins, or pdf.js 4.10.38, which needs only `Promise.try`, `Promise.withResolvers` and the base64 methods.
5. **PKCE optional** (`settings.py:890`). Requiring it would break public OAuth clients that don't send a code challenge.
6. **Dockerfile base and install.** `FROM python:3.13-trixie` is not digest-pinned; `curl ... setup_22.x | bash -` runs as root (and CI is on Node 24); `pip install -e` uses build isolation, so the build backend's own dependencies (`setuptools`, `tomli`, `importlib_metadata`) are unpinned; `ipython` and `django-extensions` ship in the production image (dropping them may break `shell_plus` users).
7. **Native binaries without provenance**: 13 `@parcel/watcher-*`, 13 `lightningcss-*`, and `fsevents`, all from individual maintainers with tokens. These run in build and dev tooling. Integrity is locked; they cannot be reviewed by reading.
8. **Opaque pickle at import**: babel's `global.dat` (see above).
9. **Unpinned runtime install in the SBOM job**: `@cyclonedx/cyclonedx-npm`, installed by `prisma-sbom-submit` on every run.
10. **Vendored JavaScript past EOL or with advisories**: Bootstrap 3.4.1 (no 3.x fix for CVE-2024-6485 and CVE-2025-1647), Vue 2.7.14 (EOL; ReDoS CVE-2024-9506), moment 2.29.1 (ReDoS CVE-2022-31129). The old jQuery 1.9.1 and 2.1.1 files are shipped but not referenced.
11. **Stripe and PayPal webhooks** have no signature check. Mitigated: both re-fetch the object from the provider API before acting. Adding the signature check is defence in depth.
12. **Not yet hashed.** The Python dependencies still resolve from ranges. A hashed lock (for example `uv lock`) would stop a newly published release from entering the next build unreviewed.

## Repository-level notes
- `docker-bake.hcl` is committed as-is (`networks = ["host"]` gives build steps the host network). The backup `docker-bake.hcl~` (ignored by `*~`) still has `push=true` and registry `cache-from`; the committed file does not.
- The repository is public: `github.com/aardbeiplantje/pretix` is readable anonymously. Pushing this branch discloses the findings above in full, so coordinate with pretix's security process (SECURITY.md) before publishing it.

## Test status
- `tests/base/test_metrics.py`: 7 passed (includes the two new regression tests, which fail on the old code).
- `tests/plugins/ticketoutputpdf`, `tests/plugins/badges`, `tests/base/test_invoices.py`, `tests/api/test_oauth.py`, `tests/base/test_metrics.py`: 108 passed on pypdf 6.21.4 (106 on baseline, plus the 2 new metrics tests).
- `tests/api/test_oauth.py`, `test_auth.py`, `test_deviceauth.py`: 58 passed on oauthlib 4.0.1.
- `tests/base/test_mail.py`: 102 passed, 1 skipped.
- Not run: the full suite, e2e, the Docker image build, a running nginx, and the GitHub/GitLab workflows themselves.

## Limitations
- Capability scanning is heuristic. A malicious payload that avoids these patterns would not be flagged; the reviews above are the complement to it.
- Attestation signatures were decoded, not verified against Sigstore roots.
- Source comparison covers 15 packages, not all. Monorepo, generated and native-binary artifacts can't be compared automatically.
- Resolution was for Python 3.12 on linux; packages gated on other markers (Windows, macOS, older Python) were not analysed.
- Each package's previous release was the only comparison point.
- Native binaries (45 npm packages) were checked for provenance and integrity only.

## Commits on `security/supply-chain-hardening` (oldest first)
- `161bd6437` Add docker-bake.hcl for building the pretix image
- `a8f90c9dd` Point Dependabot's npm updates at the root package.json
- `a1d246340` Keep local pretix.cfg and secret files out of the build context
- `579ed325c` Refuse /metrics requests when no passphrase is configured
- `e5c1f733d` Give the email image fetch a timeout
- `3f99c9ab1` Move pypdf to 6.21.x to pick up fixed PDF-parsing advisories
- `b88134481` Move oauthlib to 4.0.x and pin pretix-plugin-build
- `76bbb2b75` Pin GitHub Actions and the SBOM tool
- `708db7ac9` Pin the release and test tooling in GitLab CI
- `a21ff3d98` Pin the pip tooling and the extra packages in the image
- `1c475a17b` Stop nginx from serving ticket PDFs under /media/
- `948b871fe` Add the supply-chain analysis of pretix's pinned dependencies
- `e09474797` Run the image as an unprivileged user with root-owned code

## Reproducing the analysis

The scanner used for this report is not part of the repository. It is stdlib-only and reads each artifact in memory: it verifies hashes against the resolver and lockfile, runs the capability and diff checks described under Method, queries OSV, and compares sources against GitHub archives. Rerunning it against a newer lockfile is the way to repeat this analysis.
