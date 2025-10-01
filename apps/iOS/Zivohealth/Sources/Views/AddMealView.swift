import SwiftUI
import PhotosUI
import Combine
import UIKit


// MARK: - AddMealView
struct AddMealView: View {
    @Environment(\.dismiss) var dismiss
    @StateObject private var nutritionAPIService = NutritionAPIService.shared
    @StateObject private var nutritionManager = NutritionManager.shared
    @StateObject private var chatViewModel = ChatViewModel.shared
    
    // Combine cancellables for this view
    @State private var cancellables = Set<AnyCancellable>()
    
    // Form data
    @State private var selectedMealType: MealType = .breakfast
    @State private var foodItemName = ""
    @State private var dishName = ""
    @State private var selectedDishType: DishType = .other
    @State private var portionSize: Double = 1.0
    @State private var portionUnit = "serving"
    @State private var servingSize = ""
    @State private var calories: Double = 0
    @State private var protein: Double = 0
    @State private var carbs: Double = 0
    @State private var fat: Double = 0
    @State private var fiber: Double = 0
    @State private var sugar: Double = 0
    @State private var sodium: Double = 0
    @State private var notes = ""
    
    // Vitamins
    @State private var vitaminA: Double = 0
    @State private var vitaminC: Double = 0
    @State private var vitaminD: Double = 0
    @State private var vitaminE: Double = 0
    @State private var vitaminK: Double = 0
    @State private var thiamin: Double = 0
    @State private var riboflavin: Double = 0
    @State private var niacin: Double = 0
    @State private var vitaminB6: Double = 0
    @State private var folate: Double = 0
    @State private var vitaminB12: Double = 0
    
    // Minerals
    @State private var calcium: Double = 0
    @State private var iron: Double = 0
    @State private var magnesium: Double = 0
    @State private var phosphorus: Double = 0
    @State private var potassium: Double = 0
    @State private var zinc: Double = 0
    @State private var copper: Double = 0
    @State private var manganese: Double = 0
    @State private var selenium: Double = 0
    
    // Image selection - iOS 16+ and fallback
    @State private var selectedPhoto: Any? // Will be PhotosPickerItem? on iOS 16+
    @State private var selectedImageData: Data?
    @State private var selectedImage: UIImage?
    
    // UI states
    @State private var isAnalyzing = false
    @State private var analysisComplete = false
    @State private var showingImagePicker = false
    @State private var showingCameraPicker = false
    @State private var showingManualEntry = false
    @State private var errorMessage: String?
    @State private var showingError = false
    @State private var showingLegacyImagePicker = false
    @State private var showingPhotoSourceDialog = false
    @State private var legacySourceType: UIImagePickerController.SourceType = .photoLibrary
    @State private var didSubmitToChat = false
    @State private var chatPlaceholderMessage = "Log the nutrition using the image"
    @State private var submittedImageThumb: UIImage?
    @AppStorage("addMeal_isAnalyzing") private var persistedAnalyzing: Bool = false
    @AppStorage("addMeal_hasResponse") private var persistedHasResponse: Bool = false
    @AppStorage("addMeal_image_path") private var persistedImagePath: String = ""
    @State private var hasAssistantResponseState: Bool = false
    @State private var showManualEntryBox = false
    @State private var manualEntryText = ""
    @State private var lastSubmittedDisplayText = ""
    private enum EntryMode { case none, photo, manual }
    @State private var entryMode: EntryMode = .none
    
    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(spacing: 20) {
                    // Method Selection
                    VStack(alignment: .leading, spacing: 16) {
                        Text("How would you like to add your meal?")
                            .font(.system(size: 24, weight: .bold))
                            .foregroundColor(.primary)
                            .multilineTextAlignment(.leading)

                        HStack(spacing: 16) {
                            // Photo tile (white until selected)
                            selectionTile(
                                title: "Take Photo",
                                icon: "camera.fill",
                                selected: entryMode == .photo,
                                action: {
                                    if didSubmitToChat { return }
                                    entryMode = .photo
                                    showManualEntryBox = false
                                    showingPhotoSourceDialog = true
                                }
                            )
                            .disabled(didSubmitToChat || analyzingActive)

                            // Manual tile (white until selected)
                            selectionTile(
                                title: "Manual Entry",
                                icon: "list.bullet.rectangle.portrait",
                                selected: entryMode == .manual,
                                action: {
                                    if didSubmitToChat { return }
                                    entryMode = .manual
                                    showManualEntryBox = true
                                    // Clear any selected image when switching to manual
                                    selectedImage = nil
                                    selectedImageData = nil
                                    persistedImagePath = ""
                                }
                            )
                            .disabled(didSubmitToChat || analyzingActive)
                        }
                    }
                    .padding(.horizontal)
                    
                    // Inline Manual Entry uses the same chat placeholder area (no separate box)
                    
                    // Selected Image Card
                    if let previewImage = selectedImage {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Selected Image")
                                .font(.headline)
                            ZStack {
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(Color.gray.opacity(0.08))
                                Image(uiImage: previewImage)
                                    .resizable()
                                    .aspectRatio(contentMode: .fit)
                                    .padding(12)
                            }
                            .frame(maxHeight: 260)
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
                    
                    // Show chat placeholder when analyzing/submitted, and also for manual entry pre-submit
                    if didSubmitToChat || (persistedAnalyzing && !hasAssistantResponseState) || showManualEntryBox {
                        chatPlaceholder
                            .id("chatPlaceholderSection")
                            .onChange(of: chatViewModel.streamingContent) { _ in
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    proxy.scrollTo("chatPlaceholderSection", anchor: .bottom)
                                }
                            }
                    }

                    // Global Submit Button - visible only for photo flow after image selected
                    if entryMode == .photo && selectedImageData != nil && !didSubmitToChat {
                        Button(action: { handleGlobalSubmit() }) {
                            Text("Submit")
                                .font(.system(size: 18, weight: .bold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                                .foregroundColor(.white)
                                .background(Color.red)
                                .cornerRadius(12)
                                .shadow(color: .red.opacity(0.2), radius: 4, x: 0, y: 2)
                        }
                        .disabled(analyzingActive)
                        .opacity(analyzingActive ? 0.6 : 1.0)
                        .padding(.horizontal)
                        .padding(.bottom, 10)
                    }
                }
            }
        }
        .navigationTitle("Add Meal")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button("Back") { dismiss() }
                    .foregroundColor(.red)
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                if hasAssistantResponseState {
                    Button("Close") { dismiss() }
                        .foregroundColor(.red)
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
        // Removed ChatView navigation; manual entry uses inline placeholder box
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
            ConditionalPhotosPickerModifier(
                isPresented: $showingImagePicker,
                selectedImageData: $selectedImageData,
                selectedImage: $selectedImage
            )
        )
        .sheet(isPresented: $showingCameraPicker) {
            LegacyImagePicker(sourceType: .camera) { image in
                selectedImage = image
                selectedImageData = image.jpegData(compressionQuality: 0.8)
            }
        }
        .sheet(isPresented: $showingLegacyImagePicker) {
            LegacyImagePicker(sourceType: legacySourceType) { image in
                selectedImage = image
                selectedImageData = image.jpegData(compressionQuality: 0.8)
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
                Text(didSubmitToChat ? "Submitting to Nutrition Assistant…" : "Send to Nutrition Assistant")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                Spacer()
            }
            .padding(.bottom, 2)
            
            // When manual entry is active and before submit, show a message helper and input
            if !didSubmitToChat && showManualEntryBox {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Examples:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("• I ate chicken salad with juice for my lunch\n• I had one cup dal and white rice")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.gray.opacity(0.08))
                        .cornerRadius(10)
                    
                    // Inline message input
                    ZStack(alignment: .topLeading) {
                        if #available(iOS 16.0, *) {
                            TextEditor(text: $manualEntryText)
                                .frame(minHeight: 80, maxHeight: 120)
                                .padding(8)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 10)
                                        .stroke(Color(UIColor.systemGray4), lineWidth: 1)
                                )
                                .disabled(analyzingActive)
                        } else {
                            TextField("", text: $manualEntryText)
                                .padding(12)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 10)
                                        .stroke(Color(UIColor.systemGray4), lineWidth: 1)
                                )
                                .disabled(analyzingActive)
                        }
                        if manualEntryText.isEmpty {
                            Text("Type your meal description…")
                                .foregroundColor(.gray)
                                .padding(.top, 14)
                                .padding(.leading, 14)
                                .allowsHitTesting(false)
                        }
                    }
                    Button(action: {
                            let trimmed = manualEntryText.trimmingCharacters(in: .whitespacesAndNewlines)
                            guard !trimmed.isEmpty else { return }
                            let final = trimmed + " log this meal and dont ask any followup questions."
                            lastSubmittedDisplayText = trimmed
                            didSubmitToChat = true
                            persistedAnalyzing = true
                            Task {
                                await chatViewModel.createNewSession()
                                await chatViewModel.sendStreamingMessage(final)
                            }
                    }) {
                        Text("Submit")
                            .font(.system(size: 18, weight: .bold))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .foregroundColor(.white)
                            .background(Color.red)
                            .cornerRadius(12)
                            .shadow(color: .red.opacity(0.2), radius: 4, x: 0, y: 2)
                    }
                    .disabled(analyzingActive || manualEntryText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    .opacity(analyzingActive || manualEntryText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? 0.6 : 1.0)
                    .padding(.top, 4)
                }
            } else {
                if !(entryMode == .photo && didSubmitToChat) {
                    HStack(alignment: .top, spacing: 8) {
                        Circle().fill(Color.blue).frame(width: 24, height: 24).overlay(Text("Y").font(.caption).foregroundColor(.white))
                        Text(didSubmitToChat ? (lastSubmittedDisplayText.isEmpty ? "" : lastSubmittedDisplayText) : "Log the nutrition using the image ")
                            .font(.subheadline)
                            .foregroundColor(.primary)
                            .padding(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.blue.opacity(0.08))
                            .cornerRadius(12)
                        Spacer()
                    }
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
                            Text("Analyzing image…")
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

    // Inline Manual Entry: open chat-like message input with helper
    private var manualEntryInput: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Examples:")
                .font(.caption)
                .foregroundColor(.secondary)
            Text("• I ate chicken salad with juice for my lunch\n• I had one cup dal and white rice")
                .font(.caption)
                .foregroundColor(.secondary)
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.gray.opacity(0.08))
                .cornerRadius(10)
            ZStack(alignment: .topLeading) {
                TextEditor(text: $manualEntryText)
                    .frame(minHeight: 80, maxHeight: 120)
                    .padding(8)
                    .overlay(
                        RoundedRectangle(cornerRadius: 10)
                            .stroke(Color(UIColor.systemGray4), lineWidth: 1)
                    )
                if manualEntryText.isEmpty {
                    Text("Describe your meal…")
                        .foregroundColor(.gray)
                        .padding(.top, 14)
                        .padding(.leading, 14)
                }
            }
            HStack {
                Spacer()
                Button(action: {
                    let trimmed = manualEntryText.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !trimmed.isEmpty else { return }
                    let final = trimmed + " log this meal and dont ask any followup questions."
                    lastSubmittedDisplayText = trimmed
                    didSubmitToChat = true
                    persistedAnalyzing = true
                    Task {
                        await chatViewModel.createNewSession()
                        await chatViewModel.sendStreamingMessage(final)
                    }
                }) {
                    Text("Submit")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
                .disabled(manualEntryText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || didSubmitToChat)
                .opacity(manualEntryText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || didSubmitToChat ? 0.6 : 1.0)
            }
        }
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
        entryMode == .photo && selectedImageData != nil
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
        showManualEntryBox = false
        manualEntryText = ""
        selectedImage = nil
        selectedImageData = nil
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
            let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("meal_photo_\(UUID().uuidString).jpg")
            try? data.write(to: tempURL)
            submittedImageThumb = previewImage
            lastSubmittedDisplayText = chatPlaceholderMessage
            didSubmitToChat = true
            persistedAnalyzing = true
            Task {
                await chatViewModel.createNewSession()
                let final = chatPlaceholderMessage + " log this meal and dont ask any followup questions."
                await chatViewModel.sendStreamingMessage(final, fileURL: tempURL)
            }
        case .manual:
            let trimmed = manualEntryText.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { return }
            let final = trimmed + " log this meal and dont ask any followup questions."
            lastSubmittedDisplayText = trimmed
            didSubmitToChat = true
            persistedAnalyzing = true
            Task {
                await chatViewModel.createNewSession()
                await chatViewModel.sendStreamingMessage(final)
            }
        case .none:
            break
        }
    }

    private func persistImageDataToTemp(_ data: Data) -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("addmeal_current.jpg")
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
    
    // nutritionForm removed
    
    private func nutritionField(_ title: String, value: Binding<Double>, unit: String) -> some View {
        HStack {
            Text(title)
                .font(.subheadline)
                .frame(width: 100, alignment: .leading)
            
            Spacer()
            
            TextField("0", value: value, format: .number)
                .textFieldStyle(.roundedBorder)
                .keyboardType(.decimalPad)
                .frame(width: 80)
            
            Text(unit)
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(width: 30, alignment: .leading)
        }
    }
    
    private var isFormValid: Bool {
        !foodItemName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && 
        calories > 0
    }
    
    private func analyzeImage() {
        guard let imageData = selectedImageData else { return }
        
        isAnalyzing = true
        errorMessage = nil
        
        nutritionAPIService.analyzeFoodImage(imageData: imageData, mealType: selectedMealType)
            .sink(
                receiveCompletion: { completion in
                    DispatchQueue.main.async {
                        isAnalyzing = false
                        if case .failure(let error) = completion {
                            errorMessage = error.localizedDescription
                            showingError = true
                        }
                    }
                },
                receiveValue: { response in
                    DispatchQueue.main.async {
                        populateFormWithAnalysis(response)
                        analysisComplete = true
                    }
                }
            )
            .store(in: &cancellables)
    }
    
    private func populateFormWithAnalysis(_ response: NutritionAnalysisResponse) {
        guard let nutritionData = response.nutritionData else { return }
        
        // Populate form fields with analysis data
        dishName = nutritionData.dishName ?? ""
        if let dishTypeString = nutritionData.dishType,
           let dishType = DishType(rawValue: dishTypeString) {
            selectedDishType = dishType
        }
        servingSize = nutritionData.servingSize ?? ""
        calories = nutritionData.calories ?? 0
        protein = nutritionData.proteinG ?? 0
        carbs = nutritionData.carbsG ?? 0
        fat = nutritionData.fatG ?? 0
        fiber = nutritionData.fiberG ?? 0
        sugar = nutritionData.sugarG ?? 0
        sodium = nutritionData.sodiumMg ?? 0
        
        // Populate vitamins
        vitaminA = nutritionData.vitaminA ?? 0
        vitaminC = nutritionData.vitaminC ?? 0
        vitaminD = nutritionData.vitaminD ?? 0
        vitaminE = nutritionData.vitaminE ?? 0
        vitaminK = nutritionData.vitaminK ?? 0
        thiamin = nutritionData.thiamin ?? 0
        riboflavin = nutritionData.riboflavin ?? 0
        niacin = nutritionData.niacin ?? 0
        vitaminB6 = nutritionData.vitaminB6 ?? 0
        folate = nutritionData.folate ?? 0
        vitaminB12 = nutritionData.vitaminB12 ?? 0
        
        // Populate minerals
        calcium = nutritionData.calcium ?? 0
        iron = nutritionData.iron ?? 0
        magnesium = nutritionData.magnesium ?? 0
        phosphorus = nutritionData.phosphorus ?? 0
        potassium = nutritionData.potassium ?? 0
        zinc = nutritionData.zinc ?? 0
        copper = nutritionData.copper ?? 0
        manganese = nutritionData.manganese ?? 0
        selenium = nutritionData.selenium ?? 0
        
        // Set food item name to dish name if available
        if !dishName.isEmpty && foodItemName.isEmpty {
            foodItemName = dishName
        }
    }
    
    private func saveMeal() {
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        let timeFormatter = DateFormatter()
        timeFormatter.dateFormat = "HH:mm:ss"
        
        let currentDate = Date()
        
        let nutritionData = NutritionDataCreate(
            foodItemName: foodItemName,
            dishName: dishName.isEmpty ? nil : dishName,
            dishType: selectedDishType,
            mealType: selectedMealType,
            portionSize: portionSize,
            portionUnit: portionUnit,
            servingSize: servingSize.isEmpty ? nil : servingSize,
            calories: calories,
            proteinG: protein > 0 ? protein : nil,
            fatG: fat > 0 ? fat : nil,
            carbsG: carbs > 0 ? carbs : nil,
            fiberG: fiber > 0 ? fiber : nil,
            sugarG: sugar > 0 ? sugar : nil,
            sodiumMg: sodium > 0 ? sodium : nil,
            vitaminA: vitaminA > 0 ? vitaminA : nil, vitaminC: vitaminC > 0 ? vitaminC : nil, vitaminD: vitaminD > 0 ? vitaminD : nil, vitaminE: vitaminE > 0 ? vitaminE : nil, vitaminK: vitaminK > 0 ? vitaminK : nil,
            thiamin: thiamin > 0 ? thiamin : nil, riboflavin: riboflavin > 0 ? riboflavin : nil, niacin: niacin > 0 ? niacin : nil, vitaminB6: vitaminB6 > 0 ? vitaminB6 : nil, folate: folate > 0 ? folate : nil, vitaminB12: vitaminB12 > 0 ? vitaminB12 : nil,
            calcium: calcium > 0 ? calcium : nil, iron: iron > 0 ? iron : nil, magnesium: magnesium > 0 ? magnesium : nil, phosphorus: phosphorus > 0 ? phosphorus : nil, potassium: potassium > 0 ? potassium : nil,
            zinc: zinc > 0 ? zinc : nil, copper: copper > 0 ? copper : nil, manganese: manganese > 0 ? manganese : nil, selenium: selenium > 0 ? selenium : nil,
            mealDate: dateFormatter.string(from: currentDate),
            mealTime: timeFormatter.string(from: currentDate),
            dataSource: selectedImage != nil ? .photoAnalysis : .manualEntry,
            confidenceScore: nil,
            imageUrl: nil,
            notes: notes.isEmpty ? nil : notes
        )
        
        nutritionManager.createNutritionData(nutritionData)
        dismiss()
    }
}

// MARK: - UI Helpers
extension AddMealView {
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
                    .fill(selected ? Color.red : Color(UIColor.systemBackground))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(selected ? Color.clear : Color.gray.opacity(0.15), lineWidth: 1)
            )
            .shadow(color: selected ? Color.red.opacity(0.25) : Color.black.opacity(0.05), radius: 6, x: 0, y: 3)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Supporting Components

struct EmptyModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
    }
}

struct ConditionalPhotosPickerModifier: ViewModifier {
    @Binding var isPresented: Bool
    @Binding var selectedImageData: Data?
    @Binding var selectedImage: UIImage?
    
    func body(content: Content) -> some View {
        if #available(iOS 16.0, *) {
            content.modifier(PhotosPickerModifier(
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
struct PhotosPickerModifier: ViewModifier {
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

struct LegacyImagePicker: UIViewControllerRepresentable {
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
        let parent: LegacyImagePicker
        
        init(_ parent: LegacyImagePicker) {
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
 