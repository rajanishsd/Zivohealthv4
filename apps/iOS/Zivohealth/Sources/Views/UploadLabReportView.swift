import SwiftUI
import PhotosUI
import Combine
import UIKit


// MARK: - UploadLabReportView
struct UploadLabReportView: View {
    @Environment(\.dismiss) var dismiss
    @StateObject private var chatViewModel = ChatViewModel.shared
    
    // Combine cancellables for this view
    @State private var cancellables = Set<AnyCancellable>()
    
    // Image selection - iOS 16+ and fallback
    @State private var selectedPhoto: Any? // Will be PhotosPickerItem? on iOS 16+
    @State private var selectedImageData: Data?
    @State private var selectedImage: UIImage?
    
    // Document selection
    @State private var selectedDocumentURL: URL?
    @State private var selectedDocumentData: Data?
    @State private var selectedDocumentName: String?
    @State private var documentPickerFile: URL?
    
    // UI states
    @State private var showingImagePicker = false
    @State private var showingCameraPicker = false
    @State private var showingDocumentPicker = false
    @State private var errorMessage: String?
    @State private var showingError = false
    @State private var showingLegacyImagePicker = false
    @State private var showingPhotoSourceDialog = false
    @State private var legacySourceType: UIImagePickerController.SourceType = .photoLibrary
    @State private var didSubmitToChat = false
    @State private var chatPlaceholderMessage = "update my health record with lab reports with the uploaded file. dont any question back"
    @State private var submittedImageThumb: UIImage?
    @AppStorage("uploadLabReport_isAnalyzing") private var persistedAnalyzing: Bool = false
    @AppStorage("uploadLabReport_hasResponse") private var persistedHasResponse: Bool = false
    @AppStorage("uploadLabReport_image_path") private var persistedImagePath: String = ""
    @State private var hasAssistantResponseState: Bool = false
    @State private var lastSubmittedDisplayText = ""
    private enum EntryMode { case none, photo, document }
    @State private var entryMode: EntryMode = .none
    
    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(spacing: 20) {
                    // Method Selection
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Upload Your Lab Report")
                            .font(.system(size: 24, weight: .bold))
                            .foregroundColor(.primary)
                            .multilineTextAlignment(.leading)
                        
                        Text("Upload a file or take a photo to automatically update your health records")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.leading)

                        HStack(spacing: 16) {
                            // Upload File tile
                            selectionTile(
                                title: "Upload File",
                                icon: "doc.badge.plus",
                                selected: entryMode == .document,
                                action: {
                                    if didSubmitToChat { return }
                                    entryMode = .document
                                    showingDocumentPicker = true
                                }
                            )
                            .disabled(didSubmitToChat || analyzingActive)
                            
                            // Take Photo tile
                            selectionTile(
                                title: "Take Photo",
                                icon: "camera.fill",
                                selected: entryMode == .photo,
                                action: {
                                    if didSubmitToChat { return }
                                    entryMode = .photo
                                    showingPhotoSourceDialog = true
                                }
                            )
                            .disabled(didSubmitToChat || analyzingActive)
                        }
                    }
                    .padding(.horizontal)
                    
                    // Selected Image Card
                    if let previewImage = selectedImage {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Selected Lab Report (Photo)")
                                .font(.headline)
                            ZStack {
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(Color.gray.opacity(0.08))
                                Image(uiImage: previewImage)
                                    .resizable()
                                    .aspectRatio(contentMode: .fit)
                                    .padding(12)
                            }
                            .frame(maxHeight: 400)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(Color.gray.opacity(0.2), lineWidth: 1)
                            )
                        }
                        .padding()
                        .background(Color(UIColor.systemBackground))
                        .cornerRadius(12)
                        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
                        .padding(.horizontal)
                    }
                    
                    // Selected Document Card
                    if let docName = selectedDocumentName {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Selected Lab Report (File)")
                                .font(.headline)
                            HStack(spacing: 12) {
                                Image(systemName: "doc.fill")
                                    .font(.system(size: 40))
                                    .foregroundColor(.blue)
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(docName)
                                        .font(.subheadline)
                                        .fontWeight(.medium)
                                        .lineLimit(2)
                                    if let data = selectedDocumentData {
                                        Text("\(ByteCountFormatter.string(fromByteCount: Int64(data.count), countStyle: .file))")
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                }
                                Spacer()
                            }
                            .padding()
                            .background(Color.gray.opacity(0.08))
                            .cornerRadius(12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(Color.gray.opacity(0.2), lineWidth: 1)
                            )
                        }
                        .padding()
                        .background(Color(UIColor.systemBackground))
                        .cornerRadius(12)
                        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
                        .padding(.horizontal)
                    }
                    
                    // Show chat placeholder when analyzing/submitted
                    if didSubmitToChat || (persistedAnalyzing && !hasAssistantResponseState) {
                        chatPlaceholder
                            .id("chatPlaceholderSection")
                            .onChange(of: chatViewModel.streamingContent) { _ in
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    proxy.scrollTo("chatPlaceholderSection", anchor: .bottom)
                                }
                            }
                    }

                    // Global Submit Button - visible after file/photo selected
                    if canSubmit && !didSubmitToChat {
                        Button(action: { handleGlobalSubmit() }) {
                            Text("Submit Lab Report")
                                .font(.system(size: 18, weight: .bold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                                .foregroundColor(.white)
                                .background(Color.blue)
                                .cornerRadius(12)
                                .shadow(color: .blue.opacity(0.2), radius: 4, x: 0, y: 2)
                        }
                        .disabled(analyzingActive)
                        .opacity(analyzingActive ? 0.6 : 1.0)
                        .padding(.horizontal)
                        .padding(.bottom, 10)
                    }
                }
            }
        }
        .navigationTitle("Upload Lab Report")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button("Back") { dismiss() }
                    .foregroundColor(.blue)
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                if hasAssistantResponseState {
                    Button("Close") { dismiss() }
                        .foregroundColor(.blue)
                } else if analyzingActive {
                    Button("Close") { }
                        .disabled(true)
                } else {
                    EmptyView()
                }
            }
        }
        .onAppear {
            updateHasAssistantResponse()

            // If previous run finished, start fresh
            if persistedHasResponse {
                resetAllStateForFreshStart()
            } else if persistedAnalyzing {
                // If analyzing persisted but there's no active work, treat as stale and reset
                if !isAnalyzingNow {
                    resetAllStateForFreshStart()
                } else {
                    // Continue showing analyzing state and load image if any
                    didSubmitToChat = true
                    loadPersistedImageIfNeeded()
                }
            } else {
                // No persisted state → ensure clean selection
                resetSelectionOnly()
            }
        }
        .onChange(of: chatViewModel.messages.count) { _ in
            updateHasAssistantResponse()
        }
        .onChange(of: chatViewModel.enhancedMessages.count) { _ in
            updateHasAssistantResponse()
        }
        .confirmationDialog("Choose Photo Source", isPresented: $showingPhotoSourceDialog, titleVisibility: .visible) {
            Button("Camera") {
                if #available(iOS 16.0, *) {
                    showingCameraPicker = true
                } else {
                    legacySourceType = .camera
                    showingLegacyImagePicker = true
                }
            }
            Button("Photo Library") {
                if #available(iOS 16.0, *) {
                    showingImagePicker = true
                } else {
                    legacySourceType = .photoLibrary
                    showingLegacyImagePicker = true
                }
            }
            Button("Cancel", role: .cancel) { }
        }
        .modifier(
            ConditionalLabReportPhotosPickerModifier(
                isPresented: $showingImagePicker,
                selectedImageData: $selectedImageData,
                selectedImage: $selectedImage
            )
        )
        .sheet(isPresented: $showingCameraPicker) {
            LabReportImagePicker(sourceType: .camera) { image in
                selectedImage = image
                selectedImageData = image.jpegData(compressionQuality: 0.8)
            }
        }
        .sheet(isPresented: $showingLegacyImagePicker) {
            LabReportImagePicker(sourceType: legacySourceType) { image in
                selectedImage = image
                selectedImageData = image.jpegData(compressionQuality: 0.8)
            }
        }
        .sheet(isPresented: $showingDocumentPicker) {
            DocumentPicker(selectedFile: $documentPickerFile)
        }
        .onChange(of: documentPickerFile) { newURL in
            if let url = newURL {
                handleDocumentSelection(url: url)
                documentPickerFile = nil // Reset for next time
            }
        }
        .alert("Error", isPresented: $showingError) {
            Button("OK") { }
        } message: {
            Text(errorMessage ?? "An error occurred")
        }
        .onDisappear {
            // If there is no active analysis when leaving, clear persisted flags so buttons are enabled next time
            if !isAnalyzingNow {
                persistedAnalyzing = false
                persistedHasResponse = false
                persistedImagePath = ""
            }
        }
        .onChange(of: selectedImageData) { data in
            guard let data = data else { return }
            let url = persistImageDataToTemp(data)
            persistedImagePath = url.path
        }
    }
    
    // MARK: - Inline Chat Placeholder
    private var chatPlaceholder: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "message.fill")
                    .foregroundColor(.blue)
                Text(didSubmitToChat ? "Uploading to Health Assistant…" : "Send to Health Assistant")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                Spacer()
            }
            .padding(.bottom, 2)
            
            if !(entryMode == .photo && didSubmitToChat) {
                HStack(alignment: .top, spacing: 8) {
                    Circle().fill(Color.blue).frame(width: 24, height: 24).overlay(Text("Y").font(.caption).foregroundColor(.white))
                    Text(didSubmitToChat ? (lastSubmittedDisplayText.isEmpty ? "" : lastSubmittedDisplayText) : "Update health records with uploaded lab report")
                        .font(.subheadline)
                        .foregroundColor(.primary)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.blue.opacity(0.08))
                        .cornerRadius(12)
                    Spacer()
                }
            }
            
            // Assistant bubble or status
            if didSubmitToChat, let assistantText = latestAssistantContent {
                ScrollView {
                    HStack(alignment: .top, spacing: 8) {
                        Circle().fill(Color.gray.opacity(0.6)).frame(width: 24, height: 24).overlay(Image(systemName: "aqi.medium").font(.caption).foregroundColor(.white))
                        Text(assistantText)
                            .font(.subheadline)
                            .foregroundColor(.primary)
                            .padding(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.gray.opacity(0.08))
                            .cornerRadius(12)
                        Spacer()
                    }
                    .padding(.trailing, 6)
                }
                .frame(height: UIScreen.main.bounds.height * 0.5)
            } else if didSubmitToChat {
                ScrollView {
                    HStack(alignment: .center, spacing: 8) {
                        Circle().fill(Color.gray.opacity(0.6)).frame(width: 24, height: 24).overlay(Image(systemName: "aqi.medium").font(.caption).foregroundColor(.white))
                        HStack(spacing: 6) {
                            ProgressView().scaleEffect(0.8)
                            Text("Processing lab report…")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        .padding(10)
                        .background(Color.gray.opacity(0.08))
                        .cornerRadius(12)
                        Spacer()
                    }
                    .padding(.trailing, 6)
                }
                .frame(height: UIScreen.main.bounds.height * 0.5)
            }
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color(UIColor.systemBackground)))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.gray.opacity(0.2), lineWidth: 1))
        .frame(minHeight: 180)
    }

    private var latestAssistantContent: String? {
        if chatViewModel.isStreaming, !chatViewModel.streamingContent.isEmpty {
            return chatViewModel.streamingContent
        }
        if chatViewModel.useEnhancedMode {
            if let last = chatViewModel.enhancedMessages.last, last.role == .assistant {
                return last.content
            }
        } else {
            if let last = chatViewModel.messages.last, last.role == .assistant {
                return last.content
            }
        }
        return nil
    }

    private var isAnalyzingNow: Bool {
        chatViewModel.isTyping || chatViewModel.isLoading || chatViewModel.isAnalyzingFile || chatViewModel.isStreaming
    }
    
    private var analyzingActive: Bool {
        ((didSubmitToChat || persistedAnalyzing) && !hasAssistantResponseState)
    }

    private var canSubmit: Bool {
        (entryMode == .photo && selectedImageData != nil) || 
        (entryMode == .document && selectedDocumentData != nil)
    }

    private func updateHasAssistantResponse() {
        let hasResp: Bool
        if chatViewModel.useEnhancedMode {
            hasResp = chatViewModel.enhancedMessages.contains { $0.role == .assistant }
        } else {
            hasResp = chatViewModel.messages.contains { $0.role == .assistant }
        }
        hasAssistantResponseState = hasResp
        if hasResp {
            persistedAnalyzing = false
            persistedHasResponse = true
            persistedImagePath = ""
        }
    }

    // MARK: - Reset Helpers
    private func resetSelectionOnly() {
        entryMode = .none
        selectedImage = nil
        selectedImageData = nil
        selectedDocumentURL = nil
        selectedDocumentData = nil
        selectedDocumentName = nil
    }

    private func resetAllStateForFreshStart() {
        persistedHasResponse = false
        persistedAnalyzing = false
        persistedImagePath = ""
        didSubmitToChat = false
        hasAssistantResponseState = false
        resetSelectionOnly()
    }

    private func handleGlobalSubmit() {
        guard canSubmit else { return }
        
        switch entryMode {
        case .photo:
            guard let data = selectedImageData, let previewImage = selectedImage else { return }
            let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("lab_report_\(UUID().uuidString).jpg")
            try? data.write(to: tempURL)
            submittedImageThumb = previewImage
            lastSubmittedDisplayText = "Update health records with uploaded lab report"
            didSubmitToChat = true
            persistedAnalyzing = true
            Task {
                await chatViewModel.createNewSession()
                await chatViewModel.sendStreamingMessage(chatPlaceholderMessage, fileURL: tempURL)
            }
            
        case .document:
            guard let docURL = selectedDocumentURL else { return }
            lastSubmittedDisplayText = "Update health records with uploaded lab report file"
            didSubmitToChat = true
            persistedAnalyzing = true
            Task {
                await chatViewModel.createNewSession()
                await chatViewModel.sendStreamingMessage(chatPlaceholderMessage, fileURL: docURL)
            }
            
        case .none:
            break
        }
    }
    
    private func handleDocumentSelection(url: URL) {
        // Start accessing the security-scoped resource
        let didStartAccessing = url.startAccessingSecurityScopedResource()
        
        defer {
            if didStartAccessing {
                url.stopAccessingSecurityScopedResource()
            }
        }
        
        // Create a file coordinator for proper file access (especially for iCloud files)
        let coordinator = NSFileCoordinator()
        var error: NSError?
        
        coordinator.coordinate(readingItemAt: url, options: [.forUploading], error: &error) { (fileURL) in
            do {
                // Copy the file to a temporary location
                let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("lab_report_\(UUID().uuidString).\(fileURL.pathExtension)")
                
                // Remove if exists
                if FileManager.default.fileExists(atPath: tempURL.path) {
                    try? FileManager.default.removeItem(at: tempURL)
                }
                
                // Copy the file
                try FileManager.default.copyItem(at: fileURL, to: tempURL)
                
                // Read the data
                let data = try Data(contentsOf: tempURL)
                
                // Update UI on main thread
                DispatchQueue.main.async {
                    // Store the document info
                    self.selectedDocumentURL = tempURL
                    self.selectedDocumentData = data
                    self.selectedDocumentName = url.lastPathComponent
                    
                    // If it's an image file, also show preview
                    if ["jpg", "jpeg", "png", "heic"].contains(url.pathExtension.lowercased()) {
                        self.selectedImage = UIImage(data: data)
                    }
                }
            } catch let fileError {
                DispatchQueue.main.async {
                    self.errorMessage = "Error loading file: \(fileError.localizedDescription)"
                    self.showingError = true
                }
            }
        }
        
        // Handle coordination error
        if let error = error {
            DispatchQueue.main.async {
                self.errorMessage = "Error accessing file: \(error.localizedDescription)"
                self.showingError = true
            }
        }
    }

    private func persistImageDataToTemp(_ data: Data) -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("uploadlabreport_current.jpg")
        try? data.write(to: url)
        return url
    }
    
    private func loadPersistedImageIfNeeded() {
        guard !persistedImagePath.isEmpty else { return }
        let url = URL(fileURLWithPath: persistedImagePath)
        if let data = try? Data(contentsOf: url) {
            selectedImageData = data
            selectedImage = UIImage(data: data)
        }
    }
}

// MARK: - UI Helpers
extension UploadLabReportView {
    @ViewBuilder
    private func selectionTile(title: String, icon: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 10) {
                Image(systemName: icon)
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundColor(selected ? .white : .primary)
                Text(title)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(selected ? .white : .primary)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 108)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(selected ? Color.blue : Color(UIColor.systemBackground))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(selected ? Color.clear : Color.gray.opacity(0.15), lineWidth: 1)
            )
            .shadow(color: selected ? Color.blue.opacity(0.25) : Color.black.opacity(0.05), radius: 6, x: 0, y: 3)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Supporting Components

struct ConditionalLabReportPhotosPickerModifier: ViewModifier {
    @Binding var isPresented: Bool
    @Binding var selectedImageData: Data?
    @Binding var selectedImage: UIImage?
    
    func body(content: Content) -> some View {
        if #available(iOS 16.0, *) {
            content.modifier(LabReportPhotosPickerModifier(
                isPresented: $isPresented,
                selectedImageData: $selectedImageData,
                selectedImage: $selectedImage
            ))
        } else {
            content
        }
    }
}

@available(iOS 16.0, *)
struct LabReportPhotosPickerModifier: ViewModifier {
    @Binding var isPresented: Bool
    @Binding var selectedImageData: Data?
    @Binding var selectedImage: UIImage?
    @State private var selectedItem: PhotosPickerItem?
    
    func body(content: Content) -> some View {
        content
            .photosPicker(
                isPresented: $isPresented,
                selection: $selectedItem,
                matching: .images,
                photoLibrary: .shared()
            )
            .onChange(of: selectedItem) { item in
                Task {
                    if let item = item,
                       let data = try? await item.loadTransferable(type: Data.self) {
                        selectedImageData = data
                        selectedImage = UIImage(data: data)
                    }
                }
            }
    }
}

struct LabReportImagePicker: UIViewControllerRepresentable {
    var sourceType: UIImagePickerController.SourceType = .photoLibrary
    let onImageSelected: (UIImage) -> Void
    @Environment(\.dismiss) private var dismiss
    
    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.delegate = context.coordinator
        if UIImagePickerController.isSourceTypeAvailable(sourceType) {
            picker.sourceType = sourceType
        } else {
            picker.sourceType = .photoLibrary
        }
        return picker
    }
    
    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {
        // No updates needed
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: LabReportImagePicker
        
        init(_ parent: LabReportImagePicker) {
            self.parent = parent
        }
        
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey : Any]) {
            if let image = info[.originalImage] as? UIImage {
                parent.onImageSelected(image)
            }
            parent.dismiss()
        }
        
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.dismiss()
        }
    }
}

// MARK: - Previews

