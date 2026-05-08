#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-/tmp/gt1000-manuals}"
mkdir -p "$out_dir"

download() {
  local name="$1"
  local url="$2"
  local pdf="$out_dir/$name.pdf"
  local text="$out_dir/$name.txt"

  curl -L -sS "$url" -o "$pdf"
  pdftotext -layout "$pdf" "$text"
  printf '%s\t%s\t%s\n' "$name" "$pdf" "$text"
}

download owner https://static.roland.com/assets/media/pdf/GT-1000_eng08_W.pdf
download parameter https://static.roland.com/assets/media/pdf/GT-1000_parameter_eng13_W.pdf
download sound-list https://static.roland.com/assets/media/pdf/GT-1000_sound_eng05_W.pdf
download midi https://static.roland.com/assets/media/pdf/GT-1000-MIDI-Implementation.pdf

