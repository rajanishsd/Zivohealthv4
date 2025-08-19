import SwiftUI
import PhotosUI
import Combine
import UIKit


// MARK: - AddMealView
struct AddMealView: View {
    @Environment(\.presentationMode) var presentationMode
    @StateObject private var nutritionAPIService = NutritionAPIService.shared
    @StateObject private var nutritionManager = NutritionManager.shared
    
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
    @State private var showingManualEntry = false
    @State private var errorMessage: String?
    @State private var showingError = false
    @State private var showingLegacyImagePicker = false
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Method Selection
                    VStack(alignment: .leading, spacing: 12) {
                        Text("How would you like to add your meal?")
                            .font(.headline)
                            .foregroundColor(.primary)
                        
                        HStack(spacing: 12) {
                            // Photo Analysis Button
                            Button(action: {
                                if #available(iOS 16.0, *) {
                                    showingImagePicker = true
                                } else {
                                    showingLegacyImagePicker = true
                                }
                            }) {
                                VStack(spacing: 8) {
                                    Image(systemName: "camera.fill")
                                        .font(.title2)
                                        .foregroundColor(.white)
                                    Text("Take Photo")
                                        .font(.subheadline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.blue)
                                .cornerRadius(12)
                            }
                            
                            // Manual Entry Button
                            Button(action: {
                                showingManualEntry = true
                            }) {
                                VStack(spacing: 8) {
                                    Image(systemName: "keyboard.fill")
                                        .font(.title2)
                                        .foregroundColor(.white)
                                    Text("Manual Entry")
                                        .font(.subheadline)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
                                }
                                .frame(maxWidth: .infinity)
            .padding()
                                .background(Color.green)
                                .cornerRadius(12)
                            }
                        }
                    }
                    .padding(.horizontal)
                    
                    // Selected Image Preview
                    if let selectedImage = selectedImage {
                        VStack(spacing: 12) {
                            Text("Selected Image")
                                .font(.headline)
                            
                            Image(uiImage: selectedImage)
                                .resizable()
                                .aspectRatio(contentMode: .fit)
                                .frame(maxHeight: 200)
                                .cornerRadius(12)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 12)
                                        .stroke(Color.gray.opacity(0.3), lineWidth: 1)
                                )
                            
                            if isAnalyzing {
                                HStack {
                                    ProgressView()
                                        .scaleEffect(0.8)
                                    Text("Analyzing food image...")
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                }
                            } else if !analysisComplete {
                                Button("Analyze Image") {
                                    analyzeImage()
                                }
                                .buttonStyle(.borderedProminent)
                            }
                        }
                        .padding(.horizontal)
                    }
                    
                    // Nutrition Form (shown after analysis or for manual entry)
                    if analysisComplete || showingManualEntry {
                        nutritionForm
                    }
                }
            }
            .navigationTitle("Add Meal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        presentationMode.wrappedValue.dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Save") {
                        saveMeal()
                    }
                    .disabled(!isFormValid)
                }
            }
        }
        .modifier(
            ConditionalPhotosPickerModifier(
                isPresented: $showingImagePicker,
                selectedImageData: $selectedImageData,
                selectedImage: $selectedImage
            )
        )
        .sheet(isPresented: $showingLegacyImagePicker) {
            LegacyImagePicker { image in
                selectedImage = image
                selectedImageData = image.jpegData(compressionQuality: 0.8)
            }
        }
        .alert("Error", isPresented: $showingError) {
            Button("OK") { }
        } message: {
            Text(errorMessage ?? "An error occurred")
        }
    }
    
    private var nutritionForm: some View {
        VStack(spacing: 16) {
            // Basic Information
            VStack(alignment: .leading, spacing: 12) {
                Text("Meal Information")
                    .font(.headline)
                
                // Meal Type
                VStack(alignment: .leading, spacing: 4) {
                    Text("Meal Type")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    Picker("Meal Type", selection: $selectedMealType) {
                        ForEach(MealType.allCases, id: \.self) { mealType in
                            Text("\(mealType.emoji) \(mealType.displayName)")
                                .tag(mealType)
                        }
                    }
                    .pickerStyle(.segmented)
                }
                
                // Food Item Name
                VStack(alignment: .leading, spacing: 4) {
                    Text("Food Item")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    TextField("e.g., Grilled Chicken Salad", text: $foodItemName)
                        .textFieldStyle(.roundedBorder)
                }
                
                // Dish Name (optional)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Dish Name (Optional)")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    TextField("e.g., Caesar Salad", text: $dishName)
                        .textFieldStyle(.roundedBorder)
                }
                
                // Dish Type
                VStack(alignment: .leading, spacing: 4) {
                    Text("Dish Type")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    Picker("Dish Type", selection: $selectedDishType) {
                        ForEach(DishType.allCases, id: \.self) { dishType in
                            Text("\(dishType.emoji) \(dishType.displayName)")
                                .tag(dishType)
                        }
                    }
                    .pickerStyle(.menu)
                }
                
                // Serving Information
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Portion Size")
                            .font(.subheadline)
                            .fontWeight(.medium)
                        
                        TextField("1.0", value: $portionSize, format: .number)
                            .textFieldStyle(.roundedBorder)
                            .keyboardType(.decimalPad)
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Unit")
                            .font(.subheadline)
                            .fontWeight(.medium)
                        
                        TextField("serving", text: $portionUnit)
                            .textFieldStyle(.roundedBorder)
                    }
                }
                
                // Serving Size Description
                VStack(alignment: .leading, spacing: 4) {
                    Text("Serving Size (Optional)")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    TextField("e.g., 1 cup, 100g", text: $servingSize)
                        .textFieldStyle(.roundedBorder)
                }
            }
            
            // Nutritional Information
            VStack(alignment: .leading, spacing: 12) {
                Text("Nutritional Information")
                    .font(.headline)
                
                // Macronutrients
                VStack(spacing: 8) {
                    nutritionField("Calories", value: $calories, unit: "cal")
                    nutritionField("Protein", value: $protein, unit: "g")
                    nutritionField("Carbohydrates", value: $carbs, unit: "g")
                    nutritionField("Fat", value: $fat, unit: "g")
                    nutritionField("Fiber", value: $fiber, unit: "g")
                    nutritionField("Sugar", value: $sugar, unit: "g")
                    nutritionField("Sodium", value: $sodium, unit: "mg")
                }
            }
            
            // Vitamins Section
            VStack(alignment: .leading, spacing: 12) {
                Text("Vitamins (Optional)")
                    .font(.headline)
                
                VStack(spacing: 8) {
                    nutritionField("Vitamin A", value: $vitaminA, unit: "μg")
                    nutritionField("Vitamin C", value: $vitaminC, unit: "mg")
                    nutritionField("Vitamin D", value: $vitaminD, unit: "μg")
                    nutritionField("Vitamin E", value: $vitaminE, unit: "mg")
                    nutritionField("Vitamin K", value: $vitaminK, unit: "μg")
                    nutritionField("Thiamin (B1)", value: $thiamin, unit: "mg")
                    nutritionField("Riboflavin (B2)", value: $riboflavin, unit: "mg")
                    nutritionField("Niacin (B3)", value: $niacin, unit: "mg")
                    nutritionField("Vitamin B6", value: $vitaminB6, unit: "mg")
                    nutritionField("Folate", value: $folate, unit: "μg")
                    nutritionField("Vitamin B12", value: $vitaminB12, unit: "μg")
                }
            }
            
            // Minerals Section
            VStack(alignment: .leading, spacing: 12) {
                Text("Minerals (Optional)")
                    .font(.headline)
                
                VStack(spacing: 8) {
                    nutritionField("Calcium", value: $calcium, unit: "mg")
                    nutritionField("Iron", value: $iron, unit: "mg")
                    nutritionField("Magnesium", value: $magnesium, unit: "mg")
                    nutritionField("Phosphorus", value: $phosphorus, unit: "mg")
                    nutritionField("Potassium", value: $potassium, unit: "mg")
                    nutritionField("Zinc", value: $zinc, unit: "mg")
                    nutritionField("Copper", value: $copper, unit: "mg")
                    nutritionField("Manganese", value: $manganese, unit: "mg")
                    nutritionField("Selenium", value: $selenium, unit: "μg")
                }
            }
            
            // Notes
            VStack(alignment: .leading, spacing: 4) {
                Text("Notes (Optional)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                if #available(iOS 16.0, *) {
                    TextField("Additional notes about the meal", text: $notes, axis: .vertical)
                        .textFieldStyle(.roundedBorder)
                        .lineLimit(3...6)
                } else {
                    TextField("Additional notes about the meal", text: $notes)
                        .textFieldStyle(.roundedBorder)
                        .lineLimit(6)
                }
            }
        }
        .padding(.horizontal)
    }
    
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
        presentationMode.wrappedValue.dismiss()
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
    let onImageSelected: (UIImage) -> Void
    @Environment(\.dismiss) private var dismiss
    
    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.delegate = context.coordinator
        picker.sourceType = .photoLibrary
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
 