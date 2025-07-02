#!/bin/bash

# End-to-end test script for LogSeq to Obsidian conversion
# This script tests the convert_notes.py against the example LogSeq vault

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting LogSeq to Obsidian conversion test...${NC}"

# Define paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGSEQ_VAULT="$SCRIPT_DIR/example/logseq_vault"
OUTPUT_DIR="$SCRIPT_DIR/example/obsidian_output"
CONVERT_SCRIPT="$SCRIPT_DIR/convert_notes.py"

# Check if required files exist
if [ ! -f "$CONVERT_SCRIPT" ]; then
    echo -e "${RED}Error: convert_notes.py not found at $CONVERT_SCRIPT${NC}"
    exit 1
fi

if [ ! -d "$LOGSEQ_VAULT" ]; then
    echo -e "${RED}Error: LogSeq vault not found at $LOGSEQ_VAULT${NC}"
    exit 1
fi

# Clean up existing output directory
if [ -d "$OUTPUT_DIR" ]; then
    echo -e "${YELLOW}Removing existing output directory...${NC}"
    rm -rf "$OUTPUT_DIR"
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo -e "${YELLOW}Converting LogSeq vault to Obsidian format...${NC}"

# Run the conversion script with common flags
python3 "$CONVERT_SCRIPT" \
    --logseq "$LOGSEQ_VAULT" \
    --output "$OUTPUT_DIR" \
    --overwrite_output \
    --convert_tags_to_links

# Check if conversion was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Conversion completed successfully!${NC}"
    echo -e "${GREEN}Output saved to: $OUTPUT_DIR${NC}"
    
    # Show summary of converted files
    if [ -d "$OUTPUT_DIR" ]; then
        echo -e "${YELLOW}Conversion summary:${NC}"
        echo "Pages converted: $(find "$OUTPUT_DIR" -name "*.md" -not -path "*/journals/*" | wc -l)"
        echo "Journal entries: $(find "$OUTPUT_DIR/journals" -name "*.md" 2>/dev/null | wc -l || echo "0")"
        echo "Assets copied: $(find "$OUTPUT_DIR" -name "*" -type f -not -name "*.md" | wc -l)"
    fi
else
    echo -e "${RED}✗ Conversion failed!${NC}"
    exit 1
fi

echo -e "${GREEN}End-to-end test completed successfully!${NC}"