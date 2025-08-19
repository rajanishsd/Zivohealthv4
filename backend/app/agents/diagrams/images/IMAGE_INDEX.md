# Healthcare Agent System - Visual Diagram Index

Quick visual reference for all healthcare agent system workflow diagrams.

## 🖼️ Available Diagrams

### 1. System Architecture (357KB)
**File**: `system-architecture.png`  
**Shows**: Complete end-to-end system workflow from user request to response
- User entry points (file upload, questions)
- Enhanced Customer Agent coordination
- Document processing with OCR and classification
- Specialized agent routing and processing
- Database storage and retrieval
- OpenTelemetry monitoring
- Error handling and recovery

### 2. Document Upload Workflow (TBD)
**File**: `document-upload-workflow.png`  
**Shows**: Detailed document upload workflow in chat sessions
- Frontend chat interface integration
- API layer file validation and storage
- Enhanced Customer Agent LangGraph workflow
- Document Processing Orchestrator coordination
- Specialized health agent routing and processing
- Database operations and state management
- Response flow and error handling

### 3. Use Cases (254KB)
**File**: `use-cases.png`  
**Shows**: Three core use case workflows in detail
- **File Upload Only**: Document processing and storage
- **Question Only**: Intelligent data retrieval and response
- **File + Question**: Combined document processing and question answering

### 4. Agent Workflows (141KB)
**File**: `agent-workflows.png`  
**Shows**: Individual specialized agent mini-workflows
- **Vitals Agent**: Blood pressure, heart rate, temperature processing
- **Pharmacy Agent**: Medication bills and cost analysis
- **Lab Agent**: Laboratory test results and categorization
- **Prescription Agent**: Medication prescriptions and history

### 5. State Management (207KB)
**File**: `state-management.png`  
**Shows**: LangGraph state management and inter-agent communication
- Agent state initialization and routing
- Operation execution (extract, store, retrieve, assess)
- State updates and finalization
- Inter-agent message passing
- Memory management and checkpointing

### 6. Monitoring & Error Handling (257KB)
**File**: `monitoring-error-handling.png`  
**Shows**: OpenTelemetry monitoring and comprehensive error handling
- Trace initialization and agent span creation
- Database operation monitoring
- Error classification and recovery strategies
- Workflow coordination and parallel processing
- Performance metrics and alerting

### 7. Intelligent Retrieval (200KB)
**File**: `intelligent-retrieval.png`  
**Shows**: Agent-delegated intelligent data retrieval system
- Question assessment by all specialized agents
- Relevance scoring and strategy determination
- Selective data retrieval based on agent expertise
- Comparison with old manual classification system
- Benefits of domain expert decision making

## 📊 Total Size: ~1.6MB
All diagrams combined provide comprehensive visual documentation of the healthcare agent system architecture and workflows.

## 🎯 Quick Access
- **For presentations**: Use high-resolution PNG files
- **For documentation**: Reference both PNG and Mermaid markdown files
- **For development**: Use Mermaid files for easy editing and updates
- **For quick reference**: This index provides overview of each diagram's content 