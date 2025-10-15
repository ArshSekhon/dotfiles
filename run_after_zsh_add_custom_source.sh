#!/usr/bin/env bash
set -euo pipefail

ZSHRC="$HOME/.zshrc"
BLOCK_START="# Source all files in ~/.zsh_custom"
BLOCK_CONTENT=$(cat <<'EOF'
prompt off || true
# Source all files in ~/.zsh_custom
for file in ~/.zsh_custom/*.zsh; do
  [ -r "$file" ] && source "$file"
done
eval "$(starship init zsh)"
EOF
)

# Check if the block already exists
if grep -Fxq "$BLOCK_START" "$ZSHRC"; then
  echo "✅ ~/.zshrc already contains the custom source block!"
else
  echo "🔧 Adding custom source block to ~/.zshrc ..."
  echo -e "\n$BLOCK_CONTENT" >> "$ZSHRC"
  echo "✅ Added successfully."
fi
