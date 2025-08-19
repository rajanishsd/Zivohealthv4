# Healthcare Agent System Workflow Diagrams

This directory contains comprehensive workflow diagrams for the healthcare agent system. Each diagram is available both as Mermaid markdown files and as rendered PNG images for easy reference.

## 📋 Diagram Index

### 📝 Markdown Files (Mermaid Format)
1. **[system-architecture.md](./system-architecture.md)** - Complete system architecture and main workflow
2. **[document-upload-workflow.md](./document-upload-workflow.md)** - Detailed document upload workflow in chat sessions
3. **[use-cases.md](./use-cases.md)** - Three core use cases detailed workflows  
4. **[agent-workflows.md](./agent-workflows.md)** - Individual specialized agent mini-workflows
5. **[state-management.md](./state-management.md)** - LangGraph state management and message passing
6. **[monitoring-error-handling.md](./monitoring-error-handling.md)** - OpenTelemetry monitoring and error handling workflows
7. **[intelligent-retrieval.md](./intelligent-retrieval.md)** - Agent-delegated intelligent data retrieval workflow

### 🖼️ Rendered Images (PNG Format)
All diagrams are also available as high-resolution PNG images in the `images/` folder:

1. **[system-architecture.png](./images/system-architecture.png)** - Overall system architecture
2. **[document-upload-workflow.png](./images/document-upload-workflow.png)** - Document upload workflow in chat sessions
3. **[use-cases.png](./images/use-cases.png)** - Three core use cases workflows
4. **[agent-workflows.png](./images/agent-workflows.png)** - Individual agent workflows
5. **[state-management.png](./images/state-management.png)** - LangGraph state management
6. **[monitoring-error-handling.png](./images/monitoring-error-handling.png)** - Monitoring and error handling
7. **[intelligent-retrieval.png](./images/intelligent-retrieval.png)** - Intelligent data retrieval

## 🎯 How to View Diagrams

### Option 1: PNG Images (Immediate Viewing)
- Navigate to the `/images/` folder and open any `.png` file
- Works with any image viewer, perfect for quick reference
- High-resolution images suitable for presentations and documentation

### Option 2: GitHub/GitLab (Recommended for Mermaid)
- View directly in GitHub/GitLab which supports Mermaid rendering
- Just open any `.md` file and the diagrams will render automatically

### Option 3: Mermaid Live Editor
1. Go to [mermaid.live](https://mermaid.live)
2. Copy the Mermaid code from any diagram file
3. Paste into the editor to see the rendered diagram

### Option 4: VS Code
- Install the "Mermaid Preview" extension
- Open any diagram file and use "Preview Mermaid" command

### Option 5: Documentation Tools
- Most documentation tools (GitBook, Notion, etc.) support Mermaid
- Copy the code blocks into your preferred documentation platform

## 🏗️ Architecture Overview

The healthcare agent system uses a specialized agent architecture where:

- **Enhanced Customer Agent**: Central hub that analyzes requests and coordinates responses
- **Document Processing Orchestrator**: Handles file uploads with OCR and classification
- **Specialized Agents**: Domain experts (Vitals, Pharmacy, Lab, Prescription) with their own mini-workflows
- **Intelligent Data Retrieval**: Agents assess question relevance and determine optimal retrieval strategies
- **LangGraph State Management**: Handles complex workflows with memory and checkpointing
- **OpenTelemetry Monitoring**: Comprehensive tracing and error handling

## 🔄 Workflow Types

### Core Use Cases
1. **File Upload Only**: Process medical documents and store structured data
2. **Question Only**: Retrieve and analyze existing health data to answer questions
3. **File + Question**: Process documents AND answer questions using combined data

### Agent Operations
Each specialized agent supports four main operations:
- **Extract**: Parse and structure data from documents
- **Store**: Save structured data to appropriate database tables
- **Retrieve**: Fetch relevant data based on intelligent assessment
- **Assess**: Evaluate question relevance and determine retrieval strategy

## 📊 Data Flow

```
User Request → Customer Agent → [Document Processing OR Data Retrieval] → Specialized Agents → Database → Response Generation → User
```

## 🧠 Key Innovations

- **Agent-Delegated Intelligence**: Each agent determines what data is relevant for retrieval
- **Domain Expertise**: Specialized agents understand their data types deeply
- **Intelligent Routing**: Automatic document classification and agent routing
- **Contextual Memory**: LangGraph maintains context across interactions
- **Comprehensive Monitoring**: OpenTelemetry tracks every operation
- **Graceful Error Handling**: System continues working even with partial failures

## 🚀 Future Extensions

The architecture supports easy addition of new specialized agents:
- **ImagingAgent**: For radiology and medical imaging data
- **AllergyAgent**: For allergy and adverse reaction tracking
- **AppointmentAgent**: For healthcare appointment and scheduling data
- **InsuranceAgent**: For insurance claims and coverage data

Simply follow the same pattern: extend BaseHealthAgent, implement the four core operations, and add to the agent registry.

## 📁 File Structure

```
backend/app/agents/diagrams/
├── README.md                           # This file
├── system-architecture.md              # Complete system overview
├── use-cases.md                        # Three main use cases
├── agent-workflows.md                  # Individual agent workflows
├── state-management.md                 # LangGraph state management
├── monitoring-error-handling.md        # Error handling and monitoring
├── document-upload-workflow.md        # Document upload workflow in chat sessions
├── intelligent-retrieval.md            # Intelligent data retrieval
└── images/                             # Rendered PNG images
    ├── system-architecture.png         # 357KB - Main architecture
    ├── use-cases.png                   # 254KB - Use cases flow
    ├── agent-workflows.png             # 141KB - Agent workflows
    ├── state-management.png            # 207KB - State management
    ├── monitoring-error-handling.png   # 257KB - Monitoring & errors
    ├── intelligent-retrieval.png       # 200KB - Intelligent retrieval
    └── convert_diagrams.sh             # Conversion script
```

## 🔧 Regenerating Images

To regenerate PNG images from Mermaid files:

```bash
cd backend/app/agents/diagrams/images
chmod +x convert_diagrams.sh
./convert_diagrams.sh
```

**Note**: Requires `@mermaid-js/mermaid-cli` to be installed globally:
```bash
npm install -g @mermaid-js/mermaid-cli
``` 