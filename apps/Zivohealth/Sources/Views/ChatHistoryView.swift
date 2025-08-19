import SwiftUI
import UIKit

struct ChatHistoryView: View {
    @StateObject private var historyManager = ChatHistoryManager.shared
    @State private var selectedChatSession: ChatSessionResponse?
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @Environment(\.dismiss) private var dismiss
    let fromTab: Bool
    
    init(fromTab: Bool = false) {
        self.fromTab = fromTab
    }

    var body: some View {
        VStack(spacing: 0) {
            let sessionsWithMessages = historyManager.chatSessions.filter { ($0.messageCount ?? 0) > 0 }
            
            if sessionsWithMessages.isEmpty {
                // Empty state
                VStack(spacing: 24) {
                    Spacer()
                    
                    Image(systemName: "text.bubble.fill")
                        .font(.system(size: 64))
                        .foregroundColor(.blue.opacity(0.6))
                    
                    VStack(spacing: 8) {
                        Text("No Chat History")
                            .font(.title2)
                            .fontWeight(.semibold)
                        
                        Text("Your conversation history will appear here")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    
                    Button(action: {
                        // Create a new chat session
                        ChatViewModel.shared.createNewChat()
                    }) {
                        HStack {
                            Image(systemName: "plus.message")
                            Text("Start Your First Chat")
                        }
                        .font(.headline)
                        .foregroundColor(.white)
                        .padding()
                        
                        .cornerRadius(12)
                    }
                    
                    Spacer()
                }
                .padding()
            } else {
                List {
                    ForEach(sessionsWithMessages.sorted { 
                        ($0.lastMessageAt ?? $0.createdAt) > ($1.lastMessageAt ?? $1.createdAt) 
                    }) { session in
                        ChatSessionRow(session: session)
                            .onTapGesture {
                                selectedChatSession = session
                            }
                            .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                                Button("Delete", role: .destructive) {
                                    Task {
                                        await historyManager.deleteSession(session.id)
                                    }
                                }
                            }
                    }
                }
                .listStyle(PlainListStyle())
            }
        }
        .navigationTitle("Chat History")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                trashButton
            }
        }
        .sheet(item: $selectedChatSession) { session in
            ChatSessionDetailView(session: session, historyManager: historyManager, fromTab: fromTab, dismissParent: dismiss)
        }
        .onAppear {
            // Load chat sessions from backend
            Task {
                await historyManager.loadChatSessionsFromBackend()
            }
        }
    }
    
    @ViewBuilder
    private var trashButton: some View {
        let sessionsWithMessages = historyManager.chatSessions.filter { ($0.messageCount ?? 0) > 0 }
        if !sessionsWithMessages.isEmpty && fromTab {
            Button(action: {
                // Clear all chat history
                Task {
                    await showDeleteAllConfirmation()
                }
            }) {
                Image(systemName: "trash")
                    .foregroundColor(.red)
            }
        } else {
            EmptyView()
        }
    }
    
    private func showDeleteAllConfirmation() async {
        // Clear all chat sessions
        await historyManager.clearAllChatSessions()
    }
}

struct ChatSessionRow: View {
    let session: ChatSessionResponse
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(session.title ?? "Untitled Chat")
                    .font(.headline)
                    .lineLimit(1)
                
                HStack {
                    Text("\(session.messageCount ?? 0) messages")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Spacer()
                    
                    if let lastMessageAt = session.lastMessageAt {
                        Text(lastMessageAt, style: .relative)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        Text(session.createdAt, style: .relative)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                // Show verification and prescription indicators
                HStack(spacing: 8) {
                    if session.hasVerification == true {
                        Label("Verified", systemImage: "checkmark.seal.fill")
                            .font(.caption2)
                            .foregroundColor(.green)
                    }
                    
                    if session.hasPrescriptions == true {
                        Label("Rx", systemImage: "pills.fill")
                            .font(.caption2)
                            .foregroundColor(.blue)
                    }
                }
            }
            
            Spacer()
            
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 8)
    }
}

struct ChatSessionDetailView: View {
    let session: ChatSessionResponse
    let historyManager: ChatHistoryManager
    let fromTab: Bool
    let dismissParent: DismissAction
    
    @Environment(\.dismiss) private var dismiss

    @State private var messages: [ChatMessage] = []
    @State private var isLoading = true
    
    var body: some View {
        NavigationView {
            VStack {
                if isLoading {
                    ProgressView("Loading messages...")
                        .padding()
                } else if messages.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "message")
                            .font(.system(size: 50))
                            .foregroundColor(.gray)
                        
                        Text("No messages in this chat")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        Button("Start Chatting") {
                            ChatViewModel.shared.loadSpecificSession(session.id)
                            dismiss() // Dismiss detail view
                            dismissParent() // Dismiss parent chat history view
                            
                            // Post notification to switch to chat tab
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                                NotificationCenter.default.post(name: Notification.Name("SwitchToChatTab"), object: nil)
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .padding()
                } else {
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(messages) { message in
                                ChatMessageBubble(message: message)
                            }
                        }
                        .padding()
                    }
                    
                    Button("Continue Chat") {
                        ChatViewModel.shared.loadSpecificSession(session.id)
                        dismiss() // Dismiss detail view
                        dismissParent() // Dismiss parent chat history view
                        
                        // Post notification to switch to chat tab
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                            NotificationCenter.default.post(name: Notification.Name("SwitchToChatTab"), object: nil)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .padding(.horizontal)
                    .padding(.bottom)
                }
            }
            .background(Color(UIColor.systemBackground))
            .navigationTitle(session.title?.isEmpty == false ? session.title! : "Chat Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close") {
                        dismiss()
                    }
                }
            }

        }
        .onAppear {
            print("📱 [ChatHistoryView] Loading messages for session: \(session.id)")
            Task {
                await loadMessages()
            }
        }
    }
    
    private func loadMessages() async {
        do {
            let backendMessages = try await NetworkService.shared.getSessionMessages(session.id)
            await MainActor.run {
                messages = backendMessages.map { $0.toChatMessage() }
                isLoading = false
            }
        } catch {
            print("❌ [ChatHistoryView] Error loading messages: \(error)")
            await MainActor.run {
                messages = []
                isLoading = false
            }
        }
    }
}

struct ChatMessageBubble: View {
    let message: ChatMessage
    @State private var showTimestamp = false
    
    var body: some View {
        HStack {
            if message.role == .user {
                Spacer()
                
                VStack(alignment: .trailing, spacing: 6) {
                    // Show file attachment if present
                    if message.hasAttachment, let fileName = message.fileName {
                        HStack(spacing: 6) {
                            Image(systemName: getFileIcon(for: message.fileType))
                                .foregroundColor(.white)
                            Text("📎 \(fileName)")
                                .font(.caption)
                                .foregroundColor(.white)
                                .lineLimit(1)
                                .truncationMode(.middle)
                                .frame(maxWidth: UIScreen.main.bounds.width * 0.55, alignment: .leading)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color.blue.opacity(0.8))
                        .cornerRadius(8)
                        
                    }
                    
                    // Show message content if not empty
                    if !message.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        HStack {
                            Spacer()
                            ChatHistoryClickableTextView(
                                content: message.content,
                                isUserMessage: true
                            )
                            .padding(.horizontal, 2)
                                .padding(.vertical, 2)
                                .onTapGesture {
                                    showTimestamp.toggle()
                                }
                            
                            
                            .padding(.trailing, 8)
                        }
                    }
                }
            } else {
                VStack(alignment: .leading, spacing: 6) {
                    // Show file attachment if present  
                    if message.hasAttachment, let fileName = message.fileName {
                        HStack(spacing: 6) {
                            Image(systemName: getFileIcon(for: message.fileType))
                                .foregroundColor(.blue)
                            Text("📎 \(fileName)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                                .truncationMode(.middle)
                                .frame(maxWidth: UIScreen.main.bounds.width * 0.55, alignment: .leading)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color(UIColor.systemGray6))
                        .cornerRadius(8)
                        .fixedSize(horizontal: false, vertical: true)
                    }
                    
                    // Show message content if not empty
                    if !message.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        HStack {
                            ChatHistoryClickableTextView(
                                content: message.content,
                                isUserMessage: false
                            )
                            .padding(.horizontal, 2)
                                .padding(.vertical, 2)
                                .onTapGesture {
                                    showTimestamp.toggle()
                                }
                            .background(Color(.systemGray5))
                            
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.leading, 8)
                            Spacer()
                        }
                    }
                }
                
                Spacer()
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
}

// MARK: - ChatHistory ClickableTextView (Local Copy)

struct ChatHistoryClickableTextView: View {
    let content: String
    let isUserMessage: Bool

    var body: some View {
        ChatHistoryClickableText(
            content: content,
            textColor: isUserMessage ? UIColor.systemBlue : UIColor.label,
            fontSize: UIFont.systemFontSize * 0.9
        )
        .multilineTextAlignment(isUserMessage ? .trailing : .leading)
        .lineLimit(nil)
    }
}

struct ChatHistoryClickableText: UIViewRepresentable {
    let content: String
    let textColor: UIColor
    let fontSize: CGFloat

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
        textView.setContentHuggingPriority(.defaultLow, for: .horizontal)

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
        if textColor == UIColor.systemBlue {
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
        guard let width = proposal.width else { return nil }
        
        // Calculate the height needed for the text based on the available width
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

#Preview {
    ChatHistoryView()
} 