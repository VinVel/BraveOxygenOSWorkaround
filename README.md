# Brave for OxygenOS

This repository contains an automated GitHub Actions workflow that rebuilds the
latest Brave stable Android APKs with a different application id:

```text
com.brave.browser -> com.brave.browser_OOSW
```

The package rename is intended as a workaround for OxygenOS/Oplus builds that
block split-screen / flexible-window support for `com.brave.browser` while
allowing the same Brave code under another package name.

## Workflow

The workflow is defined in `.github/workflows/recompile-brave.yml`.

It runs daily and can also be started manually. On each run it:

1. Reads Brave's latest non-prerelease GitHub release from `brave/brave-browser`.
2. Skips the run if this repository already has a release tag named
   `oosw-<brave-tag>`.
3. Downloads:
   - `Bravearm64Universal.apk`
   - `BraveMonoarm.apk`
   - `BraveMonoarm64.apk`
   - `BraveMonox64.apk`
   - `BraveMonox86.apk`
4. Installs Java, Android build tools, and APKTool.
5. Decompiles each APK.
6. Replaces `com.brave.browser` with `com.brave.browser_OOSW`.
7. Rebuilds, zipaligns, and signs the APKs.
8. Creates a GitHub release with the rebuilt APKs.

## Required Secrets

Configure these repository secrets before running the workflow:

```text
ANDROID_KEYSTORE_BASE64
ANDROID_KEYSTORE_PASSWORD
ANDROID_KEY_ALIAS
ANDROID_KEY_PASSWORD
```

`ANDROID_KEY_PASSWORD` may be set to the same value as
`ANDROID_KEYSTORE_PASSWORD`.

Create the base64 keystore secret with:

```sh
base64 -w 0 your-release-key.jks
```

On macOS, use:

```sh
base64 -i your-release-key.jks
```
