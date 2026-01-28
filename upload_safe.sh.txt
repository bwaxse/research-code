#!/bin/bash

# NAVIGATE TO FOLDER IN WORKSPACE

# --- CONFIGURATION ---
REPO_URL="https://github.com/bwaxse/waxse-aou-toolkit"
# Test SOURCE_PATTERN
ls A*
SOURCE_PATTERN="../A*.ipynb"       # Where are the files coming from?
DEST_FOLDER="hla"   # Where do they go in the repo?

# 1. SETUP & INITIALIZE
# ---------------------
echo "Initializing Ghost Repo..."
rm -rf github-link                 # Safety clean of old runs
git clone --depth 1 "$REPO_URL" github-link
cd github-link
git config user.email "bennettwaxse@gmail.com"
git config user.name "Bennett Waxse"

# 2. PREPARE DIRECTORY
# --------------------
echo "Creating destination folder: $DEST_FOLDER"
mkdir -p "$DEST_FOLDER/notebooks"

# Copy notebooks to /notebooks subfolder and track what we copied
echo "Copying files matching: $SOURCE_PATTERN"
COPIED_FILES=()
for file in $SOURCE_PATTERN; do
    if [ -f "$file" ]; then
        cp "$file" "./$DEST_FOLDER/notebooks/"
        COPIED_FILES+=("$(basename "$file")")
        echo "  Copied: $(basename "$file")"
    fi
done

# 3. SAFETY SCRUBBING (CRITICAL)
# ------------------------------
echo "Scrubbing sensitive bucket paths from copied files..."
for file in "${COPIED_FILES[@]}"; do
    sed -i 's|gs://fc-secure-[a-zA-Z0-9_-]*|{bucket or my_bucket}|g' "$DEST_FOLDER/notebooks/$file"
done

echo "Scanning for other secrets (Tokens, Keys)..."
for file in "${COPIED_FILES[@]}"; do
    grep -Ei "api_key|token|secret|password|auth" "$DEST_FOLDER/notebooks/$file" || true
done

# 4. OUTPUT STRIPPING & CONVERSION
# --------------------------------
echo "Stripping notebook outputs from copied files..."
for file in "${COPIED_FILES[@]}"; do
    jupyter nbconvert --clear-output --inplace "$DEST_FOLDER/notebooks/$file"
done

echo "Generating .py files for Claude/Gemini (only for copied files)..."
for file in "${COPIED_FILES[@]}"; do
    jupyter nbconvert --to python --output-dir="$DEST_FOLDER" "$DEST_FOLDER/notebooks/$file"
done

# 5. CLEANUP
# ----------
# Create a local .gitignore so we don't upload pycache junk
echo "__pycache__/" > "$DEST_FOLDER/.gitignore"
echo ".ipynb_checkpoints/" >> "$DEST_FOLDER/.gitignore"

# 6. PUSH TO GITHUB
# -----------------
echo "⬆Syncing with GitHub..."
git add "$DEST_FOLDER"
git commit -m "Upload: Cleaned notebooks + Python exports for AI"
git push origin main
echo "Done! Your clean code is now on GitHub."