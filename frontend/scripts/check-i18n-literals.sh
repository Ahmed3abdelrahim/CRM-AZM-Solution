#!/usr/bin/env bash
# Constitution Principle I / PLAN.md C1's enforcement point — added after /speckit-analyze
# finding E1 (T038's import-lint equivalent for C8 already existed but C1's did not).
#
# Grep-based (not an ESLint rule) scan of frontend/app/ and frontend/components/ for JSX string
# literals — text between tags, and string-valued label/title/placeholder/aria-label props — not
# routed through a next-intl translation call (useTranslations/t(...)). Exits non-zero on any hit.
set -euo pipefail

SCAN_DIRS=("app" "components")
VIOLATIONS=0

is_translation_call() {
  # A line is fine if it calls t(...) somewhere, or is a plain import/comment/whitespace line.
  echo "$1" | grep -qE '\bt\(|useTranslations|^\s*//|^\s*\*|^\s*import '
}

for dir in "${SCAN_DIRS[@]}"; do
  [ -d "$dir" ] || continue
  while IFS= read -r -d '' file; do
    line_no=0
    while IFS= read -r line; do
      line_no=$((line_no + 1))

      # JSX text between tags: >Some literal text< — the first non-space character after '>'
      # must not be '<' or '{' (a '{...}' JSX expression, e.g. {children} or {t("key")}, is not
      # a literal). Arabic/other non-ASCII text is caught by [^<{] since grep here runs byte-wise
      # over UTF-8 and passes multi-byte sequences through untouched — \p{...} property escapes
      # are a PCRE feature and are NOT valid inside a POSIX [...] bracket expression under -E.
      if echo "$line" | grep -qE '>[[:space:]]*[^<{[:space:]][^<]*<'; then
        if ! is_translation_call "$line"; then
          echo "$file:$line_no: JSX text literal not routed through next-intl: $line"
          VIOLATIONS=$((VIOLATIONS + 1))
        fi
      fi

      # label/title/placeholder/aria-label string-valued props
      if echo "$line" | grep -qE '(label|title|placeholder|aria-label)="[^"{]+"'; then
        if ! is_translation_call "$line"; then
          echo "$file:$line_no: prop string literal not routed through next-intl: $line"
          VIOLATIONS=$((VIOLATIONS + 1))
        fi
      fi
    done < "$file"
  done < <(find "$dir" -type f \( -name '*.tsx' -o -name '*.jsx' \) -print0)
done

if [ "$VIOLATIONS" -gt 0 ]; then
  echo "check-i18n-literals: FAILED ($VIOLATIONS violation(s))"
  exit 1
fi

echo "check-i18n-literals: OK"
