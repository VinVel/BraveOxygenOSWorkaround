#!/usr/bin/env bash
set -euo pipefail

required_env=(
  BRAVE_REPO
  BRAVE_TAG
  ORIGINAL_PACKAGE
  NEW_PACKAGE
  KEYSTORE_BASE64
  KEYSTORE_PASSWORD
  KEY_ALIAS
)

for name in "${required_env[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
done

for tool in apktool zipalign apksigner gh jq curl python3; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "Missing required tool on PATH: ${tool}" >&2
    exit 1
  fi
done

KEY_PASSWORD="${KEY_PASSWORD:-${KEYSTORE_PASSWORD}}"

apks=(
  Bravearm64Universal.apk
  BraveMonoarm.apk
  BraveMonoarm64.apk
  BraveMonox64.apk
  BraveMonox86.apk
)

work_dir="${RUNNER_TEMP:-/tmp}/brave-oosw"
download_dir="${work_dir}/download"
decoded_dir="${work_dir}/decoded"
unsigned_dir="${work_dir}/unsigned"
aligned_dir="${work_dir}/aligned"
mkdir -p "${download_dir}" "${decoded_dir}" "${unsigned_dir}" "${aligned_dir}" dist

keystore="${work_dir}/signing.keystore"
printf '%s' "${KEYSTORE_BASE64}" | base64 --decode > "${keystore}"

latest_json="$(gh api "repos/${BRAVE_REPO}/releases/tags/${BRAVE_TAG}")"

for apk in "${apks[@]}"; do
  url="$(jq -r --arg name "${apk}" '.assets[] | select(.name == $name) | .browser_download_url' <<<"${latest_json}")"
  if [[ -z "${url}" || "${url}" == "null" ]]; then
    echo "Could not find ${apk} in ${BRAVE_REPO} release ${BRAVE_TAG}" >&2
    exit 1
  fi

  echo "Downloading ${apk}"
  curl -fL "${url}" -o "${download_dir}/${apk}"

  base="${apk%.apk}"
  decoded="${decoded_dir}/${base}"
  unsigned="${unsigned_dir}/${base}-unsigned.apk"
  aligned="${aligned_dir}/${base}-aligned.apk"
  output="dist/${base}_OOSW.apk"

  echo "Decoding ${apk}"
  apktool d --force --no-res --output "${decoded}" "${download_dir}/${apk}"

  echo "Renaming package in ${apk}: ${ORIGINAL_PACKAGE} -> ${NEW_PACKAGE}"
  if grep -q '^renameManifestPackage:' "${decoded}/apktool.yml"; then
    sed -i "s/^renameManifestPackage:.*/renameManifestPackage: ${NEW_PACKAGE}/" "${decoded}/apktool.yml"
  else
    printf '\nrenameManifestPackage: %s\n' "${NEW_PACKAGE}" >> "${decoded}/apktool.yml"
  fi

  original_dot_re="${ORIGINAL_PACKAGE//./\\.}"
  original_slash="${ORIGINAL_PACKAGE//./\/}"
  new_slash="${NEW_PACKAGE//./\/}"
  find "${decoded}" -type f \( \
      -name AndroidManifest.xml \
      -o -name "*.xml" \
      -o -name "*.smali" \
      -o -name "*.yml" \
    \) -print0 \
    | while IFS= read -r -d '' file; do
      if grep -Iq . "${file}"; then
        sed -i \
        -e "s/${original_dot_re}/${NEW_PACKAGE}/g" \
          -e "s#${original_slash}#${new_slash}#g" \
          "${file}"
      fi
    done

  echo "Rebuilding ${apk}"
  apktool b --output "${unsigned}" "${decoded}"

  echo "Patching binary manifest package in ${apk}"
  python3 .github/scripts/replace_axml_string.py "${unsigned}" "${ORIGINAL_PACKAGE}" "${NEW_PACKAGE}"

  echo "Aligning ${apk}"
  zipalign -f -p 4 "${unsigned}" "${aligned}"

  echo "Signing ${apk}"
  apksigner sign \
    --ks "${keystore}" \
    --ks-pass "pass:${KEYSTORE_PASSWORD}" \
    --ks-key-alias "${KEY_ALIAS}" \
    --key-pass "pass:${KEY_PASSWORD}" \
    --out "${output}" \
    "${aligned}"

  apksigner verify --verbose "${output}"

  if command -v aapt2 >/dev/null 2>&1; then
    actual_package="$(aapt2 dump packagename "${output}")"
    if [[ "${actual_package}" != "${NEW_PACKAGE}" ]]; then
      echo "Package rename failed for ${output}: expected ${NEW_PACKAGE}, got ${actual_package}" >&2
      exit 1
    fi

    if aapt2 dump xmltree "${output}" AndroidManifest.xml | grep -F "${ORIGINAL_PACKAGE}"; then
      echo "Manifest still contains ${ORIGINAL_PACKAGE}; refusing to publish ${output}" >&2
      exit 1
    fi
  fi
done
