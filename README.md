# Brave for OxygenOS

This is an unofficial project. It is not affiliated with, endorsed by, reviewed
by, or supported by Brave Software. The APKs produced by this workflow are
rebuilt and user-signed test builds, not official Brave releases.

Prefer the official Brave builds unless you specifically need this OxygenOS
split-screen workaround. Do not report issues from these rebuilt APKs to Brave
as official Brave build failures unless you can reproduce them with the official
APK.

This repository contains an automated GitHub Actions workflow that rebuilds the
latest Brave stable Android APKs with a different application id:

```text
com.brave.browser -> com.brave.browser_OOSW
```

The package rename is intended as a workaround for OxygenOS/Oplus builds that
block split-screen / flexible-window support for `com.brave.browser` while
allowing the same Brave code under another package name.

The repository is meant to make the workaround reproducible. If you fork it, use
your own Android signing key and make it clear to users that they are installing
an unofficial, user-signed browser build.

## Licensing

The scripts and workflow in this repository are licensed under MIT.

The rebuilt APKs are not MIT-licensed. They are repackaged builds of Brave
Browser and remain subject to Brave's upstream licenses, including MPL-2.0 and
the third-party licenses included in Brave/Chromium. Brave trademarks, names,
and logos remain property of Brave Software, Inc. These builds are unofficial
and not endorsed by Brave.

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

Linux:
```sh
base64 -w 0 your-release-key.keystore > your-release-key-keystore-base64.txt
```

macOS:
```sh
base64 -i your-release-key.keystore > your-release-key-keystore-base64.txt
```

Windows:
```pwsh
[System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes("your-release-key.keystore")) | New-Item your-release-key-keystore-base64.txt
```
