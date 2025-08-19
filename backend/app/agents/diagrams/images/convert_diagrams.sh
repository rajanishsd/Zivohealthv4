#!/bin/bash

# Convert diagrams to PNG images with proper configuration

echo "Converting healthcare agent system diagrams to PNG..."

# Create a temporary config file for high-quality images
cat > mermaid-config.json << 'EOF'
{
  "theme": "default",
  "flowchart": {
    "nodeSpacing": 50,
    "rankSpacing": 50,
    "curve": "basis",
    "padding": 20
  },
  "sequence": {
    "diagramMarginX": 50,
    "diagramMarginY": 10,
    "actorMargin": 50,
    "width": 150,
    "height": 65,
    "boxMargin": 10,
    "boxTextMargin": 5,
    "noteMargin": 10,
    "messageMargin": 35
  }
}
EOF

# Convert each diagram with error handling
convert_diagram() {
    local source_file="$1"
    local output_file="$2"
    local temp_file="temp-$output_file"
    
    if [ -f "$source_file" ]; then
        echo "Converting $source_file..."
        cp "$source_file" "$temp_file"
        mmdc -i "$temp_file" -o "$output_file" -w 3000 -H 2000 -c mermaid-config.json
        rm "$temp_file"
        echo "✅ Generated $output_file"
    else
        echo "⚠️  Warning: $source_file not found, skipping..."
    fi
}

# Convert all diagrams
convert_diagram "system-architecture-clean.mmd" "system-architecture.png"
convert_diagram "document-upload-workflow-clean.mmd" "document-upload-workflow.png"
convert_diagram "use-cases-clean.mmd" "use-cases.png"
convert_diagram "agent-workflows-clean.mmd" "agent-workflows.png"
convert_diagram "state-management-clean.mmd" "state-management.png"
convert_diagram "monitoring-clean.mmd" "monitoring-error-handling.png"
convert_diagram "intelligent-retrieval-clean.mmd" "intelligent-retrieval.png"

# Clean up
rm -f mermaid-config.json

echo ""
echo "🎉 Diagram conversion complete!"
echo ""
echo "Generated images:"
ls -la *.png | grep -E '\.(png)$'

echo ""
echo "📊 Image sizes:"
du -h *.png | sort -hr 