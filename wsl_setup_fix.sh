#!/bin/bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

nvm install 22
nvm alias default 22
nvm use 22

CURRENT_NODE_VERSION=$(nvm current)
export PATH="$HOME/.nvm/versions/node/$CURRENT_NODE_VERSION/bin:$PATH"
npm config set prefix "$HOME/.nvm/versions/node/$CURRENT_NODE_VERSION"

npm install -g @openai/codex
npm install -g oh-my-codex
omx setup --scope user

echo "Fix completed. Codex is now installed at: $(which codex)"
