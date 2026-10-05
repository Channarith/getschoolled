#!/usr/bin/env bash
# Print a URL that terminals and GitHub Actions logs can open with a click.
# Source this file, then call: print_terminal_link "https://salareen.com"
print_terminal_link() {
  local url="$1"
  if [[ -z "$url" ]]; then
    return 0
  fi
  # A pipe (pytest, CI log capture) is not a TTY. A bare URL is what those
  # viewers turn into a link. A real terminal also gets an OSC 8 hyperlink.
  if [[ -n "${GITHUB_ACTIONS:-}" || ! -t 1 ]]; then
    printf '%s\n' "$url"
  else
    printf '\033]8;;%s\033\\%s\033]8;;\033\\\n' "$url" "$url"
  fi
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    printf '\n[Open %s](%s)\n' "$url" "$url" >> "$GITHUB_STEP_SUMMARY"
  fi
}
