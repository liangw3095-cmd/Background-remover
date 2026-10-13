#!/bin/bash
# Cloud sessions: make sure numpy, Pillow and scipy are there for the
# sprite-background-removal scripts and tests/check_skill.py.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if python3 -c "import numpy, PIL, scipy" 2>/dev/null; then
  exit 0
fi

PIP_ROOT_USER_ACTION=ignore pip install -q --disable-pip-version-check -r "$CLAUDE_PROJECT_DIR/requirements.txt"
