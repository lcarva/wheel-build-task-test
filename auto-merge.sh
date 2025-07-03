#!/bin/bash
set -euo pipefail

# A script to automatically merge pull requests from a specific bot
# that have successful checks and are mergeable.
#
# SAFETY:
# 1. Runs in DRY RUN mode by default. Use the --execute flag to perform merges.
# 2. Fetches the LATEST check status for each PR individually before merging.
# 3. Checks for merge conflicts before attempting to merge.
#
# USAGE:
#   ./auto_merge.sh               # Dry run: Shows what would be merged.
#   ./auto_merge.sh --execute     # Actually merges the PRs.

# --- Configuration ---
# The username of the bot whose PRs you want to merge.
# BOT_AUTHOR="app/red-hat-konflux-kflux-prd-rh03"
BOT_AUTHOR='app/github-actions'
# The merge strategy to use (--merge, --squash, or --rebase).
MERGE_STRATEGY='--rebase'
# The repository to operate on.
REPO='lcarva/calunga'

# --- Script Logic ---

# Check if the script should run in execute mode or dry run mode.
EXECUTE_MODE=false
if [[ "${1:-}" == "--execute" ]]; then
  EXECUTE_MODE=true
  echo "✅ EXECUTE MODE: The script will perform merges."
else
  echo "🔍 DRY RUN MODE: The script will only report what it would do."
  echo "   (Use the --execute flag to perform merges)"
fi

echo "--------------------------------------------------"
echo "Fetching open PRs authored by '$BOT_AUTHOR'..."

# Get a list of open PR numbers from the specified bot.
# We use --jq to get just the numbers.
gh --repo "${REPO}" pr list --author "$BOT_AUTHOR" --state open --json number | jq '.[].number' | while read -r pr_number; do
  if [ -z "$pr_number" ]; then
    continue
  fi

  echo -e "\n🔎 Processing PR #$pr_number..."

  # 1. Check for merge conflicts first.
  # We use `gh pr view` with a JSON query to get the mergeable state.
  mergeable_state=$(gh --repo "${REPO}" pr view "$pr_number" --json mergeable --jq '.mergeable')

  if [[ "$mergeable_state" != "MERGEABLE" ]]; then
    echo "   ❌ Skipping PR #$pr_number: Not mergeable (State: $mergeable_state). Might have merge conflicts."
    continue
  fi
  echo "   ✅ PR #$pr_number is mergeable."

  # 2. Get the latest check status for this specific PR.
  # This avoids the caching issue of the `gh pr list --search` command.
  set +e
  checks_output=$(gh --repo "${REPO}" pr checks "$pr_number")
  set -e

  # Check if any checks are failing or pending.
  if echo "$checks_output" | grep -q -E 'fail|pending|expected'; then
    echo "   ❌ Skipping PR #$pr_number: One or more checks are failing or still pending."
    # Optional: uncomment the line below for more detailed output
    # echo "$checks_output"
    continue
  fi
  echo "   ✅ PR #$pr_number has all successful checks."

  # 3. If all checks passed and it's mergeable, proceed to merge.
  echo "   🚀 PR #$pr_number is ready to be merged."

  if $EXECUTE_MODE; then
    echo "      Merging PR #$pr_number..."
    gh --repo "${REPO}" pr merge "$pr_number" "$MERGE_STRATEGY"
    if [ $? -eq 0 ]; then
      echo "      ✅ Successfully merged PR #$pr_number."
    else
      echo "      ❌ Failed to merge PR #$pr_number."
    fi
  else
    echo "      (Dry Run) Would merge PR #$pr_number with strategy: $MERGE_STRATEGY."
  fi

done

echo "--------------------------------------------------"
echo "Script finished."
