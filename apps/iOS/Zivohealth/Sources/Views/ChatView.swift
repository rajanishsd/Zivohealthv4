import SwiftUI

struct ChatView: View {
    // Optional prefilled draft to show as the next page context
    let prefillDraft: String?
    let placeholderText: String?
    // Optional: hide verification/consultation actions for special flows
    let hideActionButtons: Bool
    // Optional: automatically send a file when the chat appears
    let initialFileURL: URL?
    let initialMessage: String?
    // Optional: suffix to append to any user-submitted message
    let messageSuffix: String?
    init(
        prefillDraft: String? = nil,
        placeholderText: String? = nil,
        hideActionButtons: Bool = false,
        initialFileURL: URL? = nil,
        initialMessage: String? = nil,
        messageSuffix: String? = nil
    ) {
        self.prefillDraft = prefillDraft
        self.placeholderText = placeholderText
        self.hideActionButtons = hideActionButtons
        self.initialFileURL = initialFileURL
        self.initialMessage = initialMessage
        self.messageSuffix = messageSuffix
    }
    @ObservedObject private var viewModel = ChatViewModel.shared
    @StateObject private var historyManager = ChatHistoryManager.shared
    @State private var messageText = ""
    @State private var showingDoctorSelection = false
    @State private var showingConsultationOptions = false
    @State private var showingChatHistory = false
    @State private var showingPrescriptions = false
    @State private var showingScheduleConsultation = false
    @FocusState private var isFocused: Bool
    @AppStorage("userMode") private var userMode: UserMode = .patient
    
    // New state variable to hold data passed back from the sheet
    @State private var verificationDataFromSheet: (request: ConsultationRequestResponse, doctor: Doctor)?

    @StateObject private var networkService = NetworkService.shared
    @State private var newMessage = ""
    @State private var showingImagePicker = false
    @State private var showingFilePicker = false
    @State private var selectedImage: UIImage?
    @State private var selectedFileURL: URL?
    @State private var keyboardHeight: CGFloat = 0
    @State private var didSendInitialFile = false

    // Computed property to create ChatSessionWithMessages for the header
    private var currentSession: ChatSessionWithMessages? {
        guard let sessionId = viewModel.currentSessionId else {
            return nil
        }
        
        return ChatSessionWithMessages(
            session: ChatSession(
                id: UUID(),
                title: "Chat Session"
            ),
            messages: viewModel.messages,
            verificationRequest: viewModel.pendingVerificationRequest,
            prescriptions: []
        )
    }
    
    // Computed property to get the current message count
    private var currentMessageCount: Int {
        return viewModel.useEnhancedMode ? viewModel.enhancedMessages.count : viewModel.messages.count
    }
    
    // Helper function to get the last message ID
    private var lastMessageId: String? {
        if viewModel.useEnhancedMode {
            return viewModel.enhancedMessages.last?.id.uuidString
        } else {
            return viewModel.messages.last?.id.uuidString
        }
    }

    var body: some View {
        VStack {
            // Network Status Indicator
            if !networkService.isNetworkAvailable || networkService.isReconnecting {
                NetworkStatusBanner(
                    isNetworkAvailable: networkService.isNetworkAvailable,
                    hasFailedSync: networkService.isReconnecting,
                    onRetry: {
                        // Reset reconnecting state to allow retry
                        networkService.isReconnecting = false
                    }
                )
            }
            
            // Chat Session Header - always show the buttons
            ChatSessionHeaderView()
            
            ScrollViewReader { proxy in
                ScrollView(.vertical, showsIndicators: true) {
                    LazyVStack(spacing: 12) {
                        // Show enhanced messages if in enhanced mode, otherwise regular messages
                        if viewModel.useEnhancedMode {
                            let _ = print("📋 [ChatView] Using enhanced mode with \(viewModel.enhancedMessages.count) messages")
                            ForEach(viewModel.enhancedMessages) { message in
                                let _ = print("📋 [ChatView] Rendering enhanced message ID: \(message.id)")
                                EnhancedMessageView(message: message)
                                    .id(message.id)
                            }
                            
                            // Show streaming content if currently streaming
                            if viewModel.isStreaming && !viewModel.streamingContent.isEmpty {
                                StreamingMessageView(content: viewModel.streamingContent)
                                    .id("streaming")
                            }
                            
                            // Show inline status message when processing (enhanced mode) - hide completely for file uploads
                            if (viewModel.isTyping || viewModel.isLoading || viewModel.isAnalyzingFile || networkService.isUploading) && 
                               !viewModel.lastInteractionWasFileUpload {
                                StatusMessageView(
                                    status: (networkService.isUploading || viewModel.isAnalyzingFile) ?
                                        (viewModel.currentUploadFilename.isEmpty ? "Analyzing file..." : "Analyzing \(viewModel.currentUploadFilename)...") :
                                        (viewModel.currentStatus.isEmpty ? (viewModel.isLoading ? "Sending message..." : "Processing...") : viewModel.currentStatus),
                                    progress: networkService.isUploading && !viewModel.isAnalyzingFile ? networkService.uploadProgress : viewModel.currentProgress,
                                    agentName: viewModel.currentAgent,
                                    isAnalyzing: viewModel.isAnalyzingFile
                                )
                                .id("status")
                            }
                        } else {
                            ForEach(viewModel.messages) { message in
                                let _ = print("📋 [ChatView] Rendering message ID: \(message.id), role: \(message.role), hasAttachment: \(message.hasAttachment)")
                                MessageView(message: message)
                                    .id(message.id)
                            }
                            
                            // Show inline status message when processing - hide completely for file uploads
                            if (viewModel.isTyping || viewModel.isLoading || viewModel.isAnalyzingFile || networkService.isUploading) && 
                               !viewModel.lastInteractionWasFileUpload {
                                StatusMessageView(
                                    status: (networkService.isUploading || viewModel.isAnalyzingFile) ?
                                        (viewModel.currentUploadFilename.isEmpty ? "Analyzing file..." : "Analyzing \(viewModel.currentUploadFilename)...") :
                                        (viewModel.currentStatus.isEmpty ? (viewModel.isLoading ? "Sending message..." : "Processing...") : viewModel.currentStatus),
                                    progress: networkService.isUploading && !viewModel.isAnalyzingFile ? networkService.uploadProgress : viewModel.currentProgress,
                                    agentName: viewModel.currentAgent,
                                    isAnalyzing: viewModel.isAnalyzingFile
                                )
                                .id("status")
                            }
                        }
                    }
                    .padding(.horizontal, 12) // Explicit horizontal padding for safe area
                    .padding(.vertical, 8)
                    .padding(.bottom, 90 + keyboardHeight) // Add bottom padding to prevent overlap with input area and keyboard
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color(UIColor.systemBackground))
                .onChange(of: currentMessageCount) { newCount in
                    // Auto-scroll to the last message when a new message is added
                    if let lastMessageId = lastMessageId {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                            withAnimation(.easeInOut(duration: 0.3)) {
                                proxy.scrollTo(lastMessageId, anchor: .bottom)
                            }
                        }
                    }
                }
                .onChange(of: viewModel.isStreaming) { isStreaming in
                    // Auto-scroll when streaming starts/ends
                    if isStreaming {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                            withAnimation(.easeInOut(duration: 0.3)) {
                                proxy.scrollTo("streaming", anchor: .bottom)
                            }
                        }
                    }
                }
                .onChange(of: viewModel.isTyping) { isTyping in
                    // Auto-scroll when status message appears
                    if isTyping || viewModel.isLoading || viewModel.isAnalyzingFile || networkService.isUploading {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                            withAnimation(.easeInOut(duration: 0.3)) {
                                proxy.scrollTo("status", anchor: .bottom)
                            }
                        }
                    }
                }
                .onChange(of: networkService.isUploading) { isUploading in
                    // Auto-scroll when upload starts
                    if isUploading {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                            withAnimation(.easeInOut(duration: 0.3)) {
                                proxy.scrollTo("status", anchor: .bottom)
                            }
                        }
                    }
                }
                .onChange(of: keyboardHeight) { height in
                    // Auto-scroll when keyboard appears
                    if height > 0 {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                if let lastMessageId = lastMessageId {
                                    proxy.scrollTo(lastMessageId, anchor: .bottom)
                                } else if viewModel.isStreaming {
                                    proxy.scrollTo("streaming", anchor: .bottom)
                                } else {
                                    proxy.scrollTo("status", anchor: .bottom)
                                }
                            }
                        }
                    }
                }
            }

            // Debug info section removed - status now shown inline with messages

            if let error = viewModel.error {
                Text("❌ Error: \(error)")
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding(.horizontal)
                    .background(Color(UIColor.systemBackground))
            }

            // Action Buttons - Only show when AI response is complete and not for file uploads
            if !hideActionButtons && userMode == .patient && 
               !viewModel.messages.isEmpty && 
               viewModel.isAIResponseComplete && 
               !viewModel.lastInteractionWasFileUpload {
                VStack(spacing: 8) {
                    // Buttons side by side
                    HStack(spacing: 8) {
                        // Verification Button
                        if !viewModel.isVerificationPending {
                            Button(action: {
                                showingDoctorSelection = true
                            }) {
                                HStack {
                                    Image(systemName: "stethoscope")
                                    Text("Verify AI Response with Doctor")
                                }
                                .font(.system(size: UIFont.systemFontSize * 0.65, weight: .medium)) // Smaller font for horizontal layout
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 8)
                                .background(Color.green)
                                .cornerRadius(10)
                            }
                        } else {
                            // Show verification pending state
                            Button(action: {}) {
                                HStack {
                                    Image(systemName: "clock")
                                    Text("Verification Pending")
                                }
                                .font(.system(size: UIFont.systemFontSize * 0.65, weight: .medium)) // Smaller font for horizontal layout
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 8)
                                .background(Color.orange)
                                .cornerRadius(10)
                            }
                            .disabled(true)
                        }

                        // Online Consultation Button
                        Button(action: {
                            showingConsultationOptions = true
                        }) {
                            HStack {
                                Image(systemName: "video.circle")
                                Text("Online Consultation/Book Visit")
                            }
                            .font(.system(size: UIFont.systemFontSize * 0.65, weight: .medium)) // Smaller font for horizontal layout
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                            .background(Color.blue)
                            .cornerRadius(10)
                        }
                    }
                    
                    // Show verification details below buttons when pending
                    if viewModel.isVerificationPending {
                        VStack(spacing: 2) {
                            if let doctor = viewModel.selectedDoctorForVerification {
                                Text("Assigned to Dr. \(doctor.fullName)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            
                            if let status = viewModel.verificationStatus {
                                Text("Status: \(status.capitalized)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.bottom, 6) // Reduced bottom padding slightly
                .background(Color(UIColor.systemBackground))
            }

            // Message Input
            MessageInputView(prefillText: prefillDraft, placeholderText: placeholderText, onSend: { message in
                Task {
                    let finalMessage = (messageSuffix != nil && !messageSuffix!.isEmpty) ? (message + " " + messageSuffix!) : message
                    await viewModel.sendStreamingMessage(finalMessage)
                }
            }, onSendWithFile: { message, fileURL in
                Task {
                    let finalMessage = (messageSuffix != nil && !messageSuffix!.isEmpty) ? (message + " " + messageSuffix!) : message
                    await viewModel.sendStreamingMessage(finalMessage, fileURL: fileURL)
                }
            }, isAnalyzing: viewModel.isAnalyzingFile)
        }
        .contentShape(Rectangle())
        .onTapGesture {
            // Dismiss keyboard when tapping outside message input
            hideKeyboard()
        }
        .navigationTitle("Chat")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            // Empty toolbar to override inherited toolbar items
        }
        .sheet(isPresented: $showingDoctorSelection, onDismiss: {
            // This is called when the DoctorSelectionView sheet is dismissed
            if let data = verificationDataFromSheet {
                print("Sheet dismissed, setting verification request in ChatViewModel.")
                ChatViewModel.shared.setVerificationRequest(data.request, doctor: data.doctor)
                verificationDataFromSheet = nil // Reset for next time
            }
        }) {
            NavigationView {
                DoctorSelectionView(
                    chatContext: getChatContext(),
                    userQuestion: getLastUserQuestion(),
                    isVerification: true,
                    onVerificationSetup: { request, doctor in
                        // This closure is called by DoctorSelectionView when ready
                        print("Verification setup callback received from DoctorSelectionView.")
                        self.verificationDataFromSheet = (request, doctor)
                        // DoctorSelectionView will then dismiss itself, triggering onDismiss above
                    }
                )
            }
        }
        .sheet(isPresented: $showingConsultationOptions, onDismiss: {
            // Switch to appointments tab when consultation is booked
            NotificationCenter.default.post(name: Notification.Name("SwitchToAppointmentsTab"), object: nil)
        }) {
            NavigationView {
                ConsultationOptionsView()
            }
        }
        .sheet(isPresented: $showingChatHistory) {
            NavigationView {
                ChatHistoryView()
            }
        }
        .sheet(isPresented: $showingPrescriptions) {
            NavigationView {
                PrescriptionsView()
            }
        }
        .sheet(isPresented: $showingScheduleConsultation) {
            NavigationView {
                ScheduleConsultationView()
            }
        }
        .onAppear {
            print("👋 [ChatView] View appeared")
            print("📱 [ChatView] Current messages count: \(viewModel.messages.count)")
            // Check verification status when view appears
            if viewModel.isVerificationPending {
                // Note: checkVerificationStatus is private, handle verification status checking here if needed
                print("⏳ [ChatView] Verification is pending")
            }
            viewModel.loadChatSessions()
            
            // Load current session messages to show recent messages
            Task {
                await viewModel.loadCurrentSessionData()
                if let fileURL = initialFileURL, !didSendInitialFile {
                    didSendInitialFile = true
                    await viewModel.sendStreamingMessage(initialMessage ?? "", fileURL: fileURL)
                }
            }
        }
        
        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("SwitchToChatTab"))) { _ in
            // Close any open sheets when switching to chat tab
            showingChatHistory = false
            showingPrescriptions = false
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)) { _ in
            // Check verification status when app becomes active
            if viewModel.isVerificationPending {
                // Note: checkVerificationStatus is private, handle verification status checking here if needed
                print("🔄 [ChatView] App became active, verification is pending")
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillChangeFrameNotification)) { notification in
            // Adjust bottom padding to account for keyboard height
            if let userInfo = notification.userInfo,
               let frame = userInfo[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect {
                let screenHeight = UIScreen.main.bounds.height
                let height = max(0, screenHeight - frame.origin.y)
                withAnimation(.easeInOut(duration: 0.25)) {
                    keyboardHeight = height
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillHideNotification)) { _ in
            withAnimation(.easeInOut(duration: 0.25)) {
                keyboardHeight = 0
            }
        }
    }



    private func getChatContext() -> String {
        // Get the last few messages for context
        let contextMessages = viewModel.messages.suffix(3)
        return contextMessages.map { "\($0.role): \($0.content)" }.joined(separator: "\n")
    }

    private func getLastUserQuestion() -> String {
        // Get the last user message
        return viewModel.messages.last { $0.role == .user }?.content ?? ""
    }
    
    private func hideKeyboard() {
        // Dismiss keyboard by resigning first responder
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }
}

// MARK: - Message Input Component
struct MessageInputView: View {
    let prefillText: String?
    let placeholderText: String?
    let onSend: (String) -> Void
    let onSendWithFile: (String, URL) -> Void
    let isAnalyzing: Bool
    @State private var messageText = ""
    @FocusState private var isFocused: Bool
    @State private var isExpanded = false
    @State private var showingAttachmentOptions = false
    @State private var showingFilePicker = false
    @State private var showingImagePicker = false
    @State private var selectedFile: URL?
    @State private var selectedFileName: String?
    @State private var selectedImage: UIImage?
    @State private var selectedImageURL: URL?
    @State private var isSending = false
    @ObservedObject private var networkService = NetworkService.shared
    
    var body: some View {
        VStack(spacing: 0) {
            Divider()
            
            // Upload progress now shown inline with messages
            
            // Show selected file indicator if file is selected
            if let fileName = selectedFileName {
                HStack {
                    Image(systemName: "paperclip")
                        .foregroundColor(.blue)
                    Text("📎 \(fileName)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                    Button("Remove") {
                        selectedFile = nil
                        selectedFileName = nil
                    }
                    .font(.caption)
                    .foregroundColor(.red)
                }
                .padding(.horizontal)
                .padding(.vertical, 4)
                .background(Color(UIColor.systemGray6))
            }
            
            // Show selected image indicator if image from camera is selected
            if let capturedImage = selectedImage {
                HStack {
                    Image(systemName: "camera.fill")
                        .foregroundColor(.blue)
                    Text("📷 Camera Photo")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                    
                    // Small image preview
                    Image(uiImage: capturedImage)
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: 30, height: 30)
                        .clipped()
                        .cornerRadius(4)
                    
                    Button("Remove") {
                        selectedImage = nil
                        selectedImageURL = nil
                    }
                    .font(.caption)
                    .foregroundColor(.red)
                }
                .padding(.horizontal)
                .padding(.vertical, 4)
                .background(Color(UIColor.systemGray6))
            }
            
            HStack {
                // Attachment options button
                Button(action: {
                    showingAttachmentOptions = true
                }) {
                    Image(systemName: "plus")
                        .font(.system(size: UIFont.systemFontSize * 0.9))
                        .foregroundColor(.blue)
                        .frame(width: 24, height: 24)
                }
                
                ZStack(alignment: .leading) {
                    if isExpanded {
                        // Expanded TextEditor when expanded
                        TextEditor(text: $messageText)
                            .font(.system(size: UIFont.systemFontSize * 0.9))
                            .frame(minHeight: 36, maxHeight: 120)
                            .background(Color.clear)
                            .focused($isFocused)
                            .disabled(isAnalyzing)
                    } else {
                        // Single line TextField when not expanded
                        TextField("", text: $messageText, onEditingChanged: { isEditing in
                            if isEditing && !isAnalyzing {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    isExpanded = true
                                }
                            }
                        })
                        .font(.system(size: UIFont.systemFontSize * 0.9))
                        .focused($isFocused)
                        .disabled(isAnalyzing)
                    }

                    if messageText.isEmpty && selectedFileName == nil && !isAnalyzing {
                        Text(placeholderText ?? "Type a message...")
                            .font(.system(size: UIFont.systemFontSize * 0.75))
                            .foregroundColor(.gray)
                            .padding(.leading, 4)
                            .allowsHitTesting(false)
                    }
                }
                .padding(8)
                .background(Color(UIColor.systemBackground))
                .overlay(
                    RoundedRectangle(cornerRadius: 18)
                        .stroke(Color(UIColor.systemGray4), lineWidth: 1)
                )
                .cornerRadius(18)
                
                .onTapGesture {
                    if !isAnalyzing {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            isExpanded = true
                            isFocused = true
                        }
                    }
                }
                .onChange(of: isFocused) { focused in
                    if !focused && !isAnalyzing {
                        // Collapse when focus is lost
                        withAnimation(.easeInOut(duration: 0.2)) {
                            isExpanded = false
                        }
                    }
                }

                Button(action: sendMessage) {
                    Image(systemName: "arrow.right.circle.fill")
                        .font(.system(size: UIFont.systemFontSize * 1.5))
                        .foregroundColor(canSendMessage ? .blue : .gray)
                }
                .disabled(!canSendMessage)
            }
            .padding()
            .background(Color(UIColor.systemBackground))
            .background(.regularMaterial)
        }
        .background(Color(UIColor.systemBackground))
        .onAppear {
            if let prefill = prefillText, messageText.isEmpty {
                messageText = prefill
                // Expand and focus to make it clear it's editable
                withAnimation(.easeInOut(duration: 0.2)) {
                    isExpanded = true
                    isFocused = true
                }
            }
        }
        .sheet(isPresented: $showingAttachmentOptions) {
            AttachmentOptionsView(
                onUploadFile: {
                    showingFilePicker = true
                },
                onTakePhoto: {
                    showingImagePicker = true
                }
            )
            .attachmentSheetStyle()
        }
        .sheet(isPresented: $showingFilePicker) {
            DocumentPicker(selectedFile: $selectedFile)
        }
        .sheet(isPresented: $showingImagePicker) {
            ImagePickerView(
                selectedImage: $selectedImage,
                selectedImageURL: $selectedImageURL,
                sourceType: .camera
            )
        }
        .onChange(of: selectedFile) { file in
            if let file = file {
                // Handle file selection - don't auto-send
                handleFileSelection(file)
            }
        }
        .onChange(of: selectedImageURL) { imageURL in
            if let imageURL = imageURL {
                // Don't call handleFileSelection for camera images to avoid duplicate indicators
                // Camera images are handled by the selectedImage indicator above
            }
        }
    }
    
    private var canSendMessage: Bool {
        // Disable sending if file analysis is in progress
        if isAnalyzing {
            return false
        }
        // Prevent double-tap submissions
        if isSending {
            return false
        }
        return !messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || selectedFile != nil || selectedImage != nil
    }
    
    private func sendMessage() {
        let message = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        
        // Prevent double-tap submissions
        guard !isSending else { return }
        isSending = true
        
        if let fileURL = selectedFile {
            // Send with file
            onSendWithFile(message, fileURL)
        } else if let imageURL = selectedImageURL {
            // Send with image from camera
            onSendWithFile(message, imageURL)
        } else if !message.isEmpty {
            // Send text only
            onSend(message)
        } else {
            // Nothing to send
            isSending = false
            return
        }
        
        // Reset the input
        messageText = ""
        selectedFile = nil
        selectedFileName = nil
        selectedImage = nil
        selectedImageURL = nil
        isFocused = false
        withAnimation(.easeInOut(duration: 0.2)) {
            isExpanded = false
        }
        
        // Reset sending state after a short delay to prevent rapid submissions
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            isSending = false
        }
    }
    
    private func handleFileSelection(_ fileURL: URL) {
        let fileName = fileURL.lastPathComponent
        let fileExtension = fileURL.pathExtension.lowercased()
        
        // Check if file type is supported
        let supportedTypes = ["jpg", "jpeg", "png", "pdf"]
        guard supportedTypes.contains(fileExtension) else {
            // Show error for unsupported file type
            return
        }
        
        // Store the selected file URL and name
        selectedFile = fileURL
        selectedFileName = fileName
    }
}

struct MessageView: View {
    let message: ChatMessage
    @ObservedObject private var viewModel = ChatViewModel.shared
    @StateObject private var networkService = NetworkService.shared
    @State private var showTimestamp = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Handle status messages differently
            if message.role == .status {
                // Status messages are centered with a special style
                HStack {
                    Spacer()
                    VStack(spacing: 4) {
                        Text(message.content)
                            .font(.caption)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(Color.orange.opacity(0.1))
                            .foregroundColor(.orange)
                            .cornerRadius(12)
                            .onTapGesture {
                                showTimestamp.toggle()
                            }
                        
                        if showTimestamp {
                            Text(message.timestamp.formatted(date: .omitted, time: .shortened))
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                    Spacer()
                }
                .padding(.vertical, 2)
            } else {
                // Regular user/assistant messages
                HStack(alignment: .bottom, spacing: 8) {


                    VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
                        VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 8) {
                            // Show file attachment if present
                            let _ = print("📋 [MessageView] Checking attachment for message \(message.id): hasAttachment=\(message.hasAttachment), fileName=\(message.fileName ?? "nil"), filePath=\(message.filePath ?? "nil")")
                            if message.hasAttachment {
                                let fileName = message.fileName ?? extractFileName(from: message.filePath)
                                let _ = print("📋 [MessageView] About to render FileAttachmentView with fileName: \(fileName)")
                                if message.role == .user {
                                    HStack {
                                        Spacer()
                                        FileAttachmentView(
                                            message: message,
                                            fileName: fileName,
                                            viewModel: viewModel,
                                            networkService: networkService
                                        )
                                        
                                            .padding(.trailing, 8)
                                    }
                                } else {
                                    HStack {
                                        FileAttachmentView(
                                            message: message,
                                            fileName: fileName,
                                            viewModel: viewModel,
                                            networkService: networkService
                                        )
                                        
                                            .padding(.leading, 8)
                                        Spacer()
                                    }
                                }
                            }
                            
                            // Show message content if not empty
                            if !message.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                                if message.role == .user {
                                    HStack {
                                        Spacer()
                                        ClickableTextView(
                                            content: message.content,
                                            isUserMessage: true
                                        )
                                        .padding(.horizontal, 12)
                                        .padding(.vertical, 8)
                                        .background(Color.gray.opacity(0.2))
                                        .cornerRadius(8)
                                        .padding(.trailing, 8)
                                    }
                                } else {
                                    HStack {
                                        ClickableTextView(
                                            content: message.content,
                                            isUserMessage: false
                                        )
                                        .padding(.horizontal, 4)
                                        .padding(.vertical, 2)
                                        .fixedSize(horizontal: false, vertical: true)
                                        .padding(.leading, 8)
                                        Spacer()
                                    }
                                }
                            }
                            
                            // Show visualizations if present
                            if message.hasVisualizations, let visualizations = message.visualizations {
                                VStack(spacing: 16) {
                                    ForEach(visualizations, id: \.id) { visualization in
                                        VisualizationView(
                                            visualization: visualization,
                                            networkService: networkService
                                        )
                                    }
                                }
                                .padding(.top, 8)
                            }
                        }

                        if showTimestamp {
                            Text(message.timestamp.formatted(date: .omitted, time: .shortened))
                                .font(.caption2)
                                .foregroundColor(.secondary)
                                .padding(.horizontal, 4)
                        }
                    }


                }
                .padding(.vertical, 2)
            }
        }
        .onAppear {
            print("💬 [MessageView] Rendering message: \(message.role.rawValue) - \(message.content.prefix(50))...")
            if message.hasAttachment {
                print("📎 [MessageView] Message has attachment: \(message.fileName ?? "unknown")")
            }
        }
    }
    
    private func getFileIcon(for fileType: String?) -> String {
        guard let fileType = fileType?.lowercased() else { return "paperclip" }
        
        switch fileType {
        case "pdf":
            return "doc.fill"
        case "jpg", "jpeg", "png":
            return "photo.fill"
        default:
            return "paperclip"
        }
    }
    
    private func extractFileName(from filePath: String?) -> String {
        guard let filePath = filePath else { return "Unknown File" }
        return URL(fileURLWithPath: filePath).lastPathComponent
    }
}

// MARK: - File Attachment View with Reactive Status
struct FileAttachmentView: View {
    let message: ChatMessage
    let fileName: String
    @ObservedObject var viewModel: ChatViewModel
    @ObservedObject var networkService: NetworkService
    
    var body: some View {
        let _ = print("📎 [FileAttachmentView] Rendering file: \(fileName)")
        
        return VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
            HStack(spacing: 6) {
                Image(systemName: getFileIcon(for: message.fileType))
                    .foregroundColor(message.role == .user ? .white : .blue)
                Text("📎 \(fileName)")
                    .font(.caption)
                    .foregroundColor(message.role == .user ? .white : .secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .frame(maxWidth: UIScreen.main.bounds.width * 0.55, alignment: .leading)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(message.role == .user ? Color.blue.opacity(0.8) : Color(UIColor.systemGray6))
            .cornerRadius(8)
            
            
            // Show inline analysis status if this file is being processed
            let shouldShow = message.role == .user && isCurrentlyAnalyzingThisFile()
            let _ = print("📎 [FileAttachmentView] Should show status for \(fileName): \(shouldShow)")
            
            if shouldShow {
                VStack(alignment: .leading, spacing: 4) {
                    Text(getCurrentAnalysisStatus())
                        .font(.caption2)
                        .foregroundColor(.blue)
                    
                    // Progress bar
                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            Rectangle()
                                .fill(Color.gray.opacity(0.3))
                                .frame(height: 2)
                            
                            Rectangle()
                                .fill(Color.blue)
                                .frame(width: geometry.size.width * getCurrentProgress(), height: 2)
                        }
                    }
                    .frame(height: 2)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 4)
            }
        }
    }
    
    private func getFileIcon(for fileType: String?) -> String {
        guard let fileType = fileType?.lowercased() else { return "paperclip" }
        
        switch fileType {
        case "pdf":
            return "doc.fill"
        case "jpg", "jpeg", "png":
            return "photo.fill"
        default:
            return "paperclip"
        }
    }
    
    private func isCurrentlyAnalyzingThisFile() -> Bool {
        let isProcessing = networkService.isUploading || viewModel.isAnalyzingFile || viewModel.isLoading
        let isFileUpload = viewModel.lastInteractionWasFileUpload
        let isCurrentFile = viewModel.currentUploadFilename == fileName
        let result = isProcessing && isFileUpload && isCurrentFile
        
        print("🔍 [FileAttachmentView] Analysis check for '\(fileName)':")
        print("   isUploading: \(networkService.isUploading)")
        print("   isAnalyzingFile: \(viewModel.isAnalyzingFile)")
        print("   isLoading: \(viewModel.isLoading)")
        print("   lastInteractionWasFileUpload: \(viewModel.lastInteractionWasFileUpload)")
        print("   currentUploadFilename: '\(viewModel.currentUploadFilename)'")
        print("   RESULT: \(result)")
        
        return result
    }
    
    private func getCurrentAnalysisStatus() -> String {
        if networkService.isUploading {
            return "Analyzing..."
        } else if viewModel.isAnalyzingFile {
            let status = viewModel.currentStatus.isEmpty ? "Analyzing..." : viewModel.currentStatus
            return status.contains("Analyzing") ? status : "Analyzing..."
        }
        return "Analyzing..."
    }
    
    private func getCurrentProgress() -> Double {
        if networkService.isUploading {
            return networkService.uploadProgress
        } else if viewModel.isAnalyzingFile {
            return viewModel.currentProgress
        }
        return 0.0
    }
}

// MARK: - Doctor Selection Components (included to ensure scope accessibility)

@MainActor
class DoctorSelectionViewModel: ObservableObject {
    @Published var doctors: [Doctor] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var lastCreatedRequest: ConsultationRequestResponse?
    @Published var selectedDoctorForCompletion: Doctor?

    private let networkService = NetworkService.shared

    init() {}

    func getAvailableDoctors() {
        print("🏥 [DoctorSelectionViewModel] Getting all available doctors...")

        isLoading = true
        error = nil

        Task {
            do {
                let availableDoctors = try await networkService.getAvailableDoctors()

                await MainActor.run {
                    self.doctors = availableDoctors
                    self.isLoading = false
                    print("✅ [DoctorSelectionViewModel] Found \(availableDoctors.count) available doctors")
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                    self.isLoading = false
                    print("❌ [DoctorSelectionViewModel] Error getting available doctors: \(error)")
                }
            }
        }
    }

    func findDoctorsByContext(_ context: String) {
        print("🔍 [DoctorSelectionViewModel] Finding doctors for context: \(context.prefix(100))...")

        isLoading = true
        error = nil

        Task {
            do {
                let foundDoctors = try await networkService.findDoctorsByContext(context)

                await MainActor.run {
                    self.doctors = foundDoctors
                    self.isLoading = false
                    print("✅ [DoctorSelectionViewModel] Found \(foundDoctors.count) doctors")
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                    self.isLoading = false
                    print("❌ [DoctorSelectionViewModel] Error finding doctors: \(error)")
                }
            }
        }
    }

    func createConsultationRequest(
        doctorId: Int,
        context: String,
        userQuestion: String,
        chatSessionId: Int? = nil
    ) {
        print("📝 [DoctorSelectionViewModel] Creating consultation request for doctor \(doctorId)")

        isLoading = true
        error = nil
        selectedDoctorForCompletion = doctors.first { $0.id == doctorId }

        Task {
            do {
                let consultationRequest = try await networkService.createConsultationRequest(
                    doctorId: doctorId,
                    context: context,
                    userQuestion: userQuestion,
                    chatSessionId: chatSessionId
                )

                await MainActor.run {
                    self.lastCreatedRequest = consultationRequest
                    self.isLoading = false
                    print("✅ [DoctorSelectionViewModel] Consultation request created: \(consultationRequest.id)")
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                    self.isLoading = false
                    self.selectedDoctorForCompletion = nil
                    print("❌ [DoctorSelectionViewModel] Error creating consultation request: \(error)")
                }
            }
        }
    }
}

struct DoctorSelectionView: View {
    let chatContext: String
    let userQuestion: String
    let isVerification: Bool
    let onVerificationSetup: (ConsultationRequestResponse, Doctor) -> Void
    
    @StateObject private var viewModel = DoctorSelectionViewModel()
    @Environment(\.dismiss) var dismiss
    @AppStorage("userMode") private var userMode: UserMode = .patient

    init(
        chatContext: String,
        userQuestion: String,
        isVerification: Bool,
        onVerificationSetup: @escaping (ConsultationRequestResponse, Doctor) -> Void
    ) {
        self.chatContext = chatContext
        self.userQuestion = userQuestion
        self.isVerification = isVerification
        self.onVerificationSetup = onVerificationSetup
    }

    var body: some View {
        VStack {
            // Show doctor selection for both verification and consultation requests
            if viewModel.isLoading && viewModel.lastCreatedRequest == nil {
                ProgressView(isVerification ? "Finding available doctors for verification..." : "Finding available doctors...")
                    .padding()
            } else if viewModel.isLoading && viewModel.lastCreatedRequest != nil {
                ProgressView(isVerification ? "Creating verification request..." : "Finalizing consultation request...")
                    .padding()
            } else if viewModel.doctors.isEmpty && !viewModel.isLoading {
                VStack(spacing: 16) {
                    Image(systemName: "stethoscope")
                        .font(.system(size: 50))
                        .foregroundColor(.gray)
                    Text("No doctors available")
                        .font(.headline)
                    Text("Please try again later or contact support")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding()
            } else {
                // Header for verification
                if isVerification {
                    VStack(spacing: 12) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 40))
                            .foregroundColor(.green)
                        
                        Text("Select Doctor for Verification")
                            .font(.headline)
                        
                        Text("Choose a doctor to verify the AI response from your conversation.")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                }
                
                ScrollView {
                    LazyVStack(spacing: 16) {
                        ForEach(viewModel.doctors) { doctor in
                            DoctorCardView(
                                doctor: doctor,
                                isVerification: isVerification,
                                onSelect: {
                                    selectDoctor(doctor)
                                }
                            )
                        }
                    }
                    .padding()
                }
            }

            if let error = viewModel.error {
                Text("❌ Error: \(error)")
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding()
            }
        }
        .navigationTitle(isVerification ? "Doctor Verification" : "Select Doctor for Consultation")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button("Cancel") {
                    dismiss()
                }
            }
        }
        .onAppear {
            if viewModel.doctors.isEmpty {
                if isVerification {
                    // For verification, get all available doctors
                    viewModel.getAvailableDoctors()
                } else {
                    // For consultation, find doctors by context
                    viewModel.findDoctorsByContext(chatContext)
                }
            }
        }
        .onChange(of: viewModel.lastCreatedRequest) { newRequest in
            if let request = newRequest,
               let doctor = viewModel.selectedDoctorForCompletion,
               viewModel.error == nil {
                print("🎁 [DoctorSelectionView] Request created, calling onVerificationSetup.")
                if isVerification {
                    onVerificationSetup(request, doctor)
                }
                dismiss()
            }
        }
    }

    private func selectDoctor(_ doctor: Doctor) {
        print("🏥 [DoctorSelectionView] Selected doctor: \(doctor.fullName) for \(isVerification ? "verification" : "consultation")")
        viewModel.selectedDoctorForCompletion = doctor
        
        // Get current session ID for verification requests
        let sessionId = isVerification ? ChatViewModel.shared.currentSessionId : nil
        
        viewModel.createConsultationRequest(
            doctorId: doctor.id,
            context: chatContext,
            userQuestion: userQuestion,
            chatSessionId: sessionId
        )
    }
}

struct DoctorCardView: View {
    let doctor: Doctor
    let isVerification: Bool
    let onSelect: () -> Void

    init(doctor: Doctor, isVerification: Bool, onSelect: @escaping () -> Void) {
        self.doctor = doctor
        self.isVerification = isVerification
        self.onSelect = onSelect
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with name and availability
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(doctor.fullName)
                        .font(Font.headline.weight(.semibold))

                    Text(doctor.specialization)
                        .font(.subheadline)
                        .foregroundColor(.blue)
                }

                Spacer()

                HStack(spacing: 4) {
                    Circle()
                        .fill(doctor.isAvailable ? Color.green : Color.red)
                        .frame(width: 8, height: 8)
                    Text(doctor.isAvailable ? "Available" : "Busy")
                        .font(.caption)
                        .foregroundColor(doctor.isAvailable ? .green : .red)
                }
            }

            // Stats
            HStack(spacing: 16) {
                StatView(
                    icon: "star.fill",
                    value: String(format: "%.1f", doctor.rating),
                    label: "Rating",
                    color: .orange
                )

                StatView(
                    icon: "clock",
                    value: "\(doctor.yearsExperience)",
                    label: "Years Exp",
                    color: .blue
                )

                StatView(
                    icon: "person.2",
                    value: "\(doctor.totalConsultations)",
                    label: "Patients",
                    color: .green
                )
            }

            // Bio
            if let bio = doctor.bio, !bio.isEmpty {
                Text(bio)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(3)
            }

            // Select button
            Button(action: onSelect) {
                HStack {
                    Image(systemName: isVerification ? "checkmark.circle" : "video")
                    Text(isVerification ? "Select for Verification" : "Request Consultation")
                }
                .font(.subheadline)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(doctor.isAvailable ? (isVerification ? Color.green : Color.blue) : Color.gray)
                .cornerRadius(12)
            }
            .disabled(!doctor.isAvailable)
        }
        .padding()
        .background(Color(UIColor.systemBackground))
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.1), radius: 4, x: 0, y: 2)
    }
}

struct StatView: View {
    let icon: String
    let value: String
    let label: String
    let color: Color

    init(icon: String, value: String, label: String, color: Color) {
        self.icon = icon
        self.value = value
        self.label = label
        self.color = color
    }

    var body: some View {
        VStack(spacing: 4) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .foregroundColor(color)
                    .font(.caption)
                Text(value)
                    .font(Font.caption.weight(.semibold))
            }

            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Chat Session Header
struct ChatSessionHeaderView: View {
    @State private var showingChatHistory = false
    @State private var showingPrescriptions = false
    @ObservedObject private var viewModel = ChatViewModel.shared
    @ObservedObject private var networkService = NetworkService.shared
    
    var body: some View {
        VStack(spacing: 8) {
            // Session title and message count
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(networkIndicatorColor)
                            .frame(width: 8, height: 8)
                        Text(viewModel.currentSessionTitle)
                            .font(.headline)
                            .fontWeight(.semibold)
                    }
                        .lineLimit(1) // Prevent text wrapping causing height changes
                        .truncationMode(.tail) // Truncate long titles
                         // Consistent width
                    
                    Text("\(viewModel.messages.count) messages")
                        .font(.caption)
                        .foregroundColor(.secondary)
                         // Consistent positioning
                }
                .frame(minHeight: 44) // Fixed minimum height to prevent layout shifts
                
                Spacer()
                
                // Essential action buttons
                HStack(spacing: 16) {
                    // Prescriptions Button
                    Button(action: {
                        showingPrescriptions = true
                    }) {
                        Image(systemName: "pills")
                            .font(.title2)
                            .foregroundColor(.red)
                            .frame(width: 28, height: 28) // Fixed button size
                    }
                    
                    // Chat History Button
                    Button(action: {
                        showingChatHistory = true
                    }) {
                        Image(systemName: "clock.arrow.circlepath")
                            .font(.title2)
                            .foregroundColor(.orange)
                            .frame(width: 28, height: 28) // Fixed button size
                    }
                    
                    // New Chat Button
                    Button(action: {
                        ChatViewModel.shared.createNewChat()
                    }) {
                        Image(systemName: "plus.circle")
                            .font(.title2)
                            .foregroundColor(.blue)
                            .frame(width: 28, height: 28) // Fixed button size
                    }
                }
                .frame(minHeight: 44) // Match the left side height
            }
            .padding(.horizontal)
            .frame(minHeight: 60) // Fixed minimum header height
            
            Divider()
        }
        .background(Color(UIColor.systemBackground))
        .sheet(isPresented: $showingChatHistory) {
            ChatHistoryView()
        }
        .sheet(isPresented: $showingPrescriptions) {
            PrescriptionsView()
        }
    }
}

private extension ChatSessionHeaderView {
    var networkIndicatorColor: Color {
        if !networkService.isNetworkAvailable { return .red }
        if networkService.isReconnecting { return .orange }
        return .green
    }
}

// NetworkStatusBanner is defined in SyncProgressView.swift

// MARK: - Enhanced Message Components

struct EnhancedMessageView: View {
    let message: EnhancedChatMessage
    @ObservedObject private var viewModel = ChatViewModel.shared
    @State private var showTimestamp = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Handle status messages differently
            if message.role == .status {
                // Status messages are centered with a special style
                HStack {
                    Spacer()
                    VStack(spacing: 4) {
                        Text(message.content)
                            .font(.caption)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(Color.orange.opacity(0.1))
                            .foregroundColor(.orange)
                            .cornerRadius(12)
                            .onTapGesture {
                                showTimestamp.toggle()
                            }
                            
                        if showTimestamp {
                            Text(message.timestamp.formatted(date: .omitted, time: .shortened))
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                    Spacer()
                }
                .padding(.vertical, 2)
            } else {
                // Regular user/assistant messages
                VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 8) {
                    // Regular message content
                    HStack(alignment: .bottom, spacing: 8) {

                        
                        VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
                            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 8) {
                                // Show file attachment if present
                                let _ = print("📋 [EnhancedMessageView] Checking attachment for message \(message.id): hasAttachment=\(message.hasAttachment), fileName=\(message.fileName ?? "nil"), filePath=\(message.filePath ?? "nil")")
                                if message.hasAttachment {
                                    let fileName = message.fileName ?? extractEnhancedFileName(from: message.filePath)
                                    let _ = print("📋 [EnhancedMessageView] About to render enhanced FileAttachmentView with fileName: \(fileName)")
                                    if message.role == .user {
                                        HStack {
                                            Spacer()
                                            EnhancedFileAttachmentView(
                                                message: message,
                                                fileName: fileName,
                                                viewModel: viewModel,
                                                networkService: NetworkService.shared
                                            )
                                            
                                            .padding(.trailing, 8)
                                        }
                                    } else {
                                        HStack {
                                            EnhancedFileAttachmentView(
                                                message: message,
                                                fileName: fileName,
                                                viewModel: viewModel,
                                                networkService: NetworkService.shared
                                            )
                                            
                                            .padding(.leading, 8)
                                            Spacer()
                                        }
                                    }
                                }
                                
                                // Show message content if not empty
                                if !message.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                                    if message.role == .user {
                                        HStack {
                                            Spacer()
                                            ClickableTextView(
                                                content: message.content,
                                                isUserMessage: true
                                            )
                                            .padding(.horizontal, 12)
                                            .padding(.vertical, 8)
                                            .background(Color.gray.opacity(0.2))
                                            .cornerRadius(8)
                                            .onTapGesture {
                                                showTimestamp.toggle()
                                            }
                                            .padding(.trailing, 8)
                                        }
                                    } else {
                                        HStack {
                                            ClickableTextView(
                                                content: message.content,
                                                isUserMessage: false
                                            )
                                            .padding(.horizontal, 2)
                                            .padding(.vertical, 2)
                                            .onTapGesture {
                                                showTimestamp.toggle()
                                            }
                                            
                                            .fixedSize(horizontal: false, vertical: true)
                                            
                                            .padding(.leading, 8)
                                            Spacer()
                                        }
                                    }
                                }
                                
                                // Show visualizations if present
                                if message.hasVisualizations, let visualizations = message.visualizations {
                                    VStack(spacing: 16) {
                                        ForEach(visualizations, id: \.id) { visualization in
                                            VisualizationView(
                                                visualization: visualization,
                                                networkService: NetworkService.shared
                                            )
                                        }
                                    }
                                                                    .padding(.top, 8)
                            }
                        }
                        
                        if showTimestamp {
                            Text(message.timestamp.formatted(date: .omitted, time: .shortened))
                                .font(.caption2)
                                .foregroundColor(.secondary)
                                .padding(.horizontal, 4)
                        }
                        }
                        

                    }
                    
                    // Quick replies for assistant messages
                    if message.role == .assistant, let quickReplies = message.quickReplies, !quickReplies.isEmpty {
                        QuickRepliesView(replies: quickReplies)
                    }
                }
                .padding(.vertical, 2)
            }
        }
    }
    
    private func getFileIcon(for fileType: String?) -> String {
        guard let fileType = fileType?.lowercased() else { return "paperclip" }
        
        switch fileType {
        case "pdf":
            return "doc.fill"
        case "jpg", "jpeg", "png":
            return "photo.fill"
        default:
            return "paperclip"
        }
    }
    
    private func extractEnhancedFileName(from filePath: String?) -> String {
        guard let filePath = filePath else { return "Unknown File" }
        return URL(fileURLWithPath: filePath).lastPathComponent
    }
}

// MARK: - Enhanced File Attachment View with Reactive Status
struct EnhancedFileAttachmentView: View {
    let message: EnhancedChatMessage
    let fileName: String
    @ObservedObject var viewModel: ChatViewModel
    @ObservedObject var networkService: NetworkService
    
    var body: some View {
        let _ = print("📎 [EnhancedFileAttachmentView] Rendering file: \(fileName)")
        
        return VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
            HStack(spacing: 6) {
                Image(systemName: getFileIcon(for: message.fileType))
                    .foregroundColor(message.role == .user ? .white : .blue)
                Text("📎 \(fileName)")
                    .font(.caption)
                    .foregroundColor(message.role == .user ? .white : .secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .frame(maxWidth: UIScreen.main.bounds.width * 0.55, alignment: .leading)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(message.role == .user ? Color.blue.opacity(0.8) : Color(UIColor.systemGray6))
            .cornerRadius(8)
            
            
            // Show inline analysis status if this file is being processed
            let shouldShow = message.role == .user && isCurrentlyAnalyzingThisFile()
            let _ = print("📎 [EnhancedFileAttachmentView] Should show status for \(fileName): \(shouldShow)")
            
            if shouldShow {
                VStack(alignment: .leading, spacing: 4) {
                    Text(getCurrentAnalysisStatus())
                        .font(.caption2)
                        .foregroundColor(.blue)
                    
                    // Progress bar
                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            Rectangle()
                                .fill(Color.gray.opacity(0.3))
                                .frame(height: 2)
                            
                            Rectangle()
                                .fill(Color.blue)
                                .frame(width: geometry.size.width * getCurrentProgress(), height: 2)
                        }
                    }
                    .frame(height: 2)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 4)
            }
        }
    }
    
    private func getFileIcon(for fileType: String?) -> String {
        guard let fileType = fileType?.lowercased() else { return "paperclip" }
        
        switch fileType {
        case "pdf":
            return "doc.fill"
        case "jpg", "jpeg", "png":
            return "photo.fill"
        default:
            return "paperclip"
        }
    }
    
    private func isCurrentlyAnalyzingThisFile() -> Bool {
        let isProcessing = networkService.isUploading || viewModel.isAnalyzingFile || viewModel.isLoading
        let isFileUpload = viewModel.lastInteractionWasFileUpload
        let isCurrentFile = viewModel.currentUploadFilename == fileName
        let result = isProcessing && isFileUpload && isCurrentFile
        
        print("🔍 [EnhancedFileAttachmentView] Analysis check for '\(fileName)':")
        print("   isUploading: \(networkService.isUploading)")
        print("   isAnalyzingFile: \(viewModel.isAnalyzingFile)")
        print("   isLoading: \(viewModel.isLoading)")
        print("   lastInteractionWasFileUpload: \(viewModel.lastInteractionWasFileUpload)")
        print("   currentUploadFilename: '\(viewModel.currentUploadFilename)'")
        print("   RESULT: \(result)")
        
        return result
    }
    
    private func getCurrentAnalysisStatus() -> String {
        if networkService.isUploading {
            return "Analyzing..."
        } else if viewModel.isAnalyzingFile {
            let status = viewModel.currentStatus.isEmpty ? "Analyzing..." : viewModel.currentStatus
            return status.contains("Analyzing") ? status : "Analyzing..."
        }
        return "Analyzing..."
    }
    
    private func getCurrentProgress() -> Double {
        if networkService.isUploading {
            return networkService.uploadProgress
        } else if viewModel.isAnalyzingFile {
            return viewModel.currentProgress
        }
        return 0.0
    }
}

struct QuickRepliesView: View {
    let replies: [QuickReply]
    @ObservedObject private var viewModel = ChatViewModel.shared
    
    var body: some View {
        LazyVGrid(columns: [
            GridItem(.flexible()),
            GridItem(.flexible())
        ], spacing: 8) {
            ForEach(replies, id: \.value) { reply in
                Button(action: {
                    viewModel.handleQuickReply(reply)
                }) {
                    Text(reply.text)
                        .font(.caption)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(Color.blue.opacity(0.1))
                        .foregroundColor(.blue)
                        .cornerRadius(16)    
                        
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.leading, 20) // Align with assistant message
    }
}

struct StreamingMessageView: View {
    let content: String
    
    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(content)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(Color(UIColor.systemGray5))
                        .foregroundColor(.primary)
                        
                        
                            
                                
                        
                    
                    // Animated typing cursor
                    Text("▋")
                        .foregroundColor(.blue)
                        .animation(.easeInOut(duration: 0.6).repeatForever(), value: true)
                }
                
                Text("now")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 4)
            }
            
            Spacer(minLength: 50)
        }
        .padding(.vertical, 2)
    }
}

struct StatusMessageView: View {
    let status: String
    let progress: Double
    let agentName: String
    let isAnalyzing: Bool
    
    @State private var dotScales: [Double] = [1.0, 1.0, 1.0]
    @State private var animationTimer: Timer?
    
    private func dotScale(for index: Int) -> Double {
        return dotScales[index]
    }
    
    private func startDotAnimation() {
        animationTimer?.invalidate()
        animationTimer = Timer.scheduledTimer(withTimeInterval: 0.6, repeats: true) { _ in
            withAnimation(.easeInOut(duration: 0.3)) {
                // Animate each dot with a delay
                for index in 0..<3 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + Double(index) * 0.2) {
                        dotScales[index] = dotScales[index] == 1.0 ? 1.5 : 1.0
                    }
                }
            }
        }
    }
    
    private func stopDotAnimation() {
        animationTimer?.invalidate()
        animationTimer = nil
        dotScales = [1.0, 1.0, 1.0]
    }
    
    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            Spacer(minLength: 50)
            
            VStack(alignment: .trailing, spacing: 4) {
                HStack(spacing: 8) {
                    // Animated dots
                    HStack(spacing: 4) {
                        ForEach(0..<3) { index in
                            Circle()
                                .fill(isAnalyzing ? Color.orange : Color.blue)
                                .frame(width: 4, height: 4)
                                .scaleEffect(dotScale(for: index))
                                .onAppear {
                                    startDotAnimation()
                                }
                                .onDisappear {
                                    stopDotAnimation()
                                }
                        }
                    }
                    
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(status)
                            .font(.subheadline.weight(.medium))
                            .foregroundColor(isAnalyzing ? .orange : .blue)
                        
                        // Removed agent name display to keep only processing text
                        
                        if progress > 0 && progress < 1.0 {
                            ProgressView(value: progress)
                                .frame(width: 120)
                                .scaleEffect(0.9)
                                .tint(isAnalyzing ? .orange : .blue)
                        }
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                Text("now")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 4)
            }
        }
        .padding(.vertical, 2)
    }
}


// MARK: - ClickableTextView

struct ClickableTextView: View {
    let content: String
    let isUserMessage: Bool

    var body: some View {
        ClickableText(
            content: content,
            textColor: isUserMessage ? UIColor.black : UIColor.label,
            fontSize: UIFont.systemFontSize * 0.9,
            isUserMessage: isUserMessage
        )
        .multilineTextAlignment(isUserMessage ? .trailing : .leading)
        .lineLimit(nil)
    }
}

struct ClickableText: UIViewRepresentable {
    let content: String
    let textColor: UIColor
    let fontSize: CGFloat
    let isUserMessage: Bool

    func makeUIView(context: Context) -> UITextView {
        let textView = UITextView()
        textView.isEditable = false
        textView.isScrollEnabled = false
        textView.backgroundColor = UIColor.clear
        textView.textContainerInset = UIEdgeInsets.zero
        textView.textContainer.lineFragmentPadding = 0

        // Enable link detection and interaction
        textView.dataDetectorTypes = [.link, .phoneNumber, .address]
        textView.isSelectable = true
        textView.isUserInteractionEnabled = true

        // Configure link appearance
        textView.linkTextAttributes = [
            .foregroundColor: textColor == UIColor.white ? UIColor.cyan : UIColor.systemBlue,
            .underlineStyle: NSUnderlineStyle.single.rawValue
        ]

        // Proper sizing
        textView.textContainer.widthTracksTextView = true
        textView.textContainer.maximumNumberOfLines = 0
        textView.scrollsToTop = false
        textView.textContainer.lineBreakMode = .byWordWrapping
        // Enable proper sizing and alignment
        textView.setContentCompressionResistancePriority(.required, for: .vertical)
        textView.setContentHuggingPriority(.required, for: .vertical)
        textView.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        // For user messages (black text), use high content hugging priority to make bubble hug content
        if textColor == UIColor.black {
            textView.setContentHuggingPriority(.required, for: .horizontal)
            textView.setContentCompressionResistancePriority(.required, for: .horizontal)
        } else {
            textView.setContentHuggingPriority(.defaultLow, for: .horizontal)
        }

        return textView
    }

    func updateUIView(_ uiView: UITextView, context: Context) {
        let attributedString = NSMutableAttributedString(string: content)
        let range = NSRange(location: 0, length: content.count)

        // Set base attributes
        attributedString.addAttributes([
            .font: UIFont.systemFont(ofSize: fontSize),
            .foregroundColor: textColor
        ], range: range)

        uiView.attributedText = attributedString
        
        // Set text alignment based on message type
        if textColor == UIColor.black {
            uiView.textAlignment = .right
        } else {
            uiView.textAlignment = .left
        }

        // Update link attributes to match the current text color
        uiView.linkTextAttributes = [
            .foregroundColor: textColor == UIColor.white ? UIColor.cyan : UIColor.systemBlue,
            .underlineStyle: NSUnderlineStyle.single.rawValue
        ]
    }
    
    @available(iOS 16.0, *)
    func sizeThatFits(_ proposal: ProposedViewSize, uiView: UITextView, context: Context) -> CGSize? {
        // For user messages, we want to hug the content
        if isUserMessage {
            let attributedString = NSMutableAttributedString(string: content)
            let range = NSRange(location: 0, length: content.count)
            attributedString.addAttributes([
                .font: UIFont.systemFont(ofSize: fontSize),
                .foregroundColor: textColor
            ], range: range)
            
            // Calculate the ideal size needed for the text
            let maxWidth = min(proposal.width ?? CGFloat.greatestFiniteMagnitude, UIScreen.main.bounds.width * 0.75)
            let boundingRect = attributedString.boundingRect(
                with: CGSize(width: maxWidth, height: CGFloat.greatestFiniteMagnitude),
                options: [.usesLineFragmentOrigin, .usesFontLeading],
                context: nil
            )
            
            let idealWidth = min(ceil(boundingRect.width), maxWidth)
            let idealHeight = ceil(boundingRect.height)
            
            return CGSize(width: idealWidth, height: idealHeight)
        } else {
            // For assistant messages, use the full available width
            guard let width = proposal.width else { return nil }
            
            let attributedString = NSMutableAttributedString(string: content)
            let range = NSRange(location: 0, length: content.count)
            attributedString.addAttributes([
                .font: UIFont.systemFont(ofSize: fontSize),
                .foregroundColor: textColor
            ], range: range)
            
            let boundingRect = attributedString.boundingRect(
                with: CGSize(width: width, height: CGFloat.greatestFiniteMagnitude),
                options: [.usesLineFragmentOrigin, .usesFontLeading],
                context: nil
            )
            
            return CGSize(width: width, height: ceil(boundingRect.height))
        }
    }
}

#Preview {
    ChatView()
}
