import SwiftUI
import Combine

// MARK: - Simple Dynamic Biomarkers Card
struct SimpleDynamicBiomarkersCard: View {
    @Binding var categories: [SimpleBiomarkerCategory]
    @Binding var isLoading: Bool
    @State private var cancellables = Set<AnyCancellable>()
    
    // Keep the original initializer for backward compatibility
    init() {
        self._categories = .constant([])
        self._isLoading = .constant(true)
        self.loadCategoriesDataInternal()
    }
    
    // New initializer with bindings
    init(categories: Binding<[SimpleBiomarkerCategory]>, isLoading: Binding<Bool>) {
        self._categories = categories
        self._isLoading = isLoading
    }
    
    private let categoryConfigs: [(String, String, Color)] = [
        ("Diabetes Panel", "drop.fill", .green),
        ("Thyroid Profile", "bolt.fill", .purple),
        ("Lipid Profile", "waveform.path.ecg", .red),
        ("Complete Blood Count (CBC)", "drop.circle.fill", .red),
        ("Liver Function Tests (LFT)", "leaf.fill", .brown),
        ("Kidney Function Tests (KFT)", "drop.triangle", .cyan),
        ("Electrolyte Panel", "atom", .blue),
        ("Infection Markers", "shield.fill", .orange),
        ("Vitamin & Mineral Panel", "pills", .green),
        ("Cardiac Markers", "heart.fill", .pink),
        ("Urine Routine", "drop.circle", .yellow),
        ("Others", "doc.text", .gray)
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "doc.text.fill")
                    .foregroundColor(.blue)
                    .font(.title2)
                Text("Biomarkers")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                if isLoading {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }
            
            // Categories List
            VStack(spacing: 12) {
                ForEach(categories, id: \.name) { category in
                    SimpleCategoryRowView(category: category)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
        .onAppear {
            if categories.isEmpty {
                loadCategoriesData()
            }
        }
    }
    
    private func loadCategoriesDataInternal() {
        // This method is for backward compatibility when using the default initializer
        DispatchQueue.main.async {
            self.loadCategoriesData()
        }
    }
    
    private func loadCategoriesData() {
        print("🔄 [SimpleDynamicBiomarkersCard] Starting to load categories data...")
        isLoading = true
        
        // Initialize categories with loading state
        categories = categoryConfigs.map { (name, icon, color) in
            SimpleBiomarkerCategory(
                name: name,
                icon: icon,
                iconColor: color,
                greenCount: 0,
                amberCount: 0,
                redCount: 0,
                totalTests: 0,
                isLoading: true
            )
        }
        
        // Load data for each category one by one
        loadNextCategory(index: 0)
    }
    
    private func loadNextCategory(index: Int) {
        guard index < categories.count else {
            isLoading = false
            print("✅ [SimpleDynamicBiomarkersCard] All categories loaded")
            return
        }
        
        let categoryName = categories[index].name
        print("📊 [SimpleDynamicBiomarkersCard] Loading data for: \(categoryName)")
        
        // Use special API method for Others category
        let publisher: AnyPublisher<CategoryTestsResponse, Error>
        if categoryName == "Others" {
            publisher = LabReportsAPIService.shared.getOthersAndUncategorizedTestsData()
        } else {
            publisher = LabReportsAPIService.shared.getCategoryTestsData(category: categoryName)
        }
        
        publisher
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { completion in
                    if case .failure(let error) = completion {
                        print("❌ [SimpleDynamicBiomarkersCard] Error loading \(categoryName): \(error)")
                        // Update with empty data on error
                        self.categories[index] = SimpleBiomarkerCategory(
                            name: categoryName,
                            icon: self.categories[index].icon,
                            iconColor: self.categories[index].iconColor,
                            greenCount: 0,
                            amberCount: 0,
                            redCount: 0,
                            totalTests: 0,
                            isLoading: false
                        )
                    }
                    
                    // Load next category after a short delay
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                        self.loadNextCategory(index: index + 1)
                    }
                },
                receiveValue: { response in
                    print("✅ [SimpleDynamicBiomarkersCard] Loaded \(categoryName): \(response.tests.count) tests")
                    
                    // Calculate status counts using same logic as individual panel views
                    let greenCount = response.tests.filter { test in
                        let status = self.convertStatus(test.status)
                        return status == "normal"
                    }.count
                    
                    let amberCount = response.tests.filter { test in
                        let status = self.convertStatus(test.status)
                        return status == "elevated"
                    }.count
                    
                    let redCount = response.tests.filter { test in
                        let status = self.convertStatus(test.status)
                        return status == "critical"
                    }.count
                    
                    // Update category with real data
                    self.categories[index] = SimpleBiomarkerCategory(
                        name: categoryName,
                        icon: self.categories[index].icon,
                        iconColor: self.categories[index].iconColor,
                        greenCount: greenCount,
                        amberCount: amberCount,
                        redCount: redCount,
                        totalTests: response.tests.count,
                        isLoading: false
                    )
                }
            )
            .store(in: &cancellables)
    }
    
    // Add the same status conversion logic as individual panel views
    private func convertStatus(_ statusString: String) -> String {
        switch statusString.lowercased() {
        case "normal", "green":
            return "normal"
        case "elevated", "high", "amber", "orange":
            return "elevated"
        case "critical", "red":
            return "critical"
        default:
            return "normal"  // Same default as DiabetesPanelView
        }
    }
}

// MARK: - Simple Category Row View
struct SimpleCategoryRowView: View {
    let category: SimpleBiomarkerCategory
    
    var body: some View {
        NavigationLink(destination: destinationView(for: category.name)) {
            categoryContent
        }
        .buttonStyle(.plain)
    }
    
    @ViewBuilder
    private func destinationView(for categoryName: String) -> some View {
        switch categoryName {
        case "Diabetes Panel":
            DiabetesPanelView()
                .navigationBarHidden(true)
        case "Thyroid Profile":
            ThyroidProfileView()
                .navigationBarHidden(true)
        case "Lipid Profile":
            LipidProfileView()
                .navigationBarHidden(true)
        case "Complete Blood Count (CBC)":
            CompleteBloodCountView()
                .navigationBarHidden(true)
        case "Liver Function Tests (LFT)":
            LiverFunctionTestsView()
                .navigationBarHidden(true)
        case "Kidney Function Tests (KFT)":
            KidneyFunctionTestsView()
                .navigationBarHidden(true)
        case "Electrolyte Panel":
            ElectrolytePanelView()
                .navigationBarHidden(true)
        case "Infection Markers":
            InfectionMarkersView()
                .navigationBarHidden(true)
        case "Vitamin & Mineral Panel":
            VitaminMineralPanelView()
                .navigationBarHidden(true)
        case "Cardiac Markers":
            CardiacMarkersView()
                .navigationBarHidden(true)
        case "Urine Routine":
            UrineRoutineView()
                .navigationBarHidden(true)
        case "Others":
            OthersView()
                .navigationBarHidden(true)
        default:
            Text("Coming Soon: \(categoryName)")
                .navigationTitle(categoryName)
        }
    }
    
    private var categoryContent: some View {
        HStack(spacing: 16) {
            // Category icon
            Image(systemName: category.icon)
                .font(.title2)
                .foregroundColor(category.iconColor)
                .frame(width: 32, height: 32)
            
            VStack(alignment: .leading, spacing: 8) {
                // Category name
                Text(category.name)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.primary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                
                // Status dots or loading indicator
                HStack(spacing: 8) {
                    if category.isLoading {
                        ProgressView()
                            .scaleEffect(0.6)
                        Text("Loading...")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        StatusDot(count: category.greenCount, color: .green)
                        StatusDot(count: category.amberCount, color: .orange)
                        StatusDot(count: category.redCount, color: .red)
                    }
                    Spacer()
                }
                
                // Total tests
                Text(category.isLoading ? "..." : "\(category.totalTests) tests")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            // Chevron
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(16)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
}

// MARK: - Simple Biomarker Category Model
struct SimpleBiomarkerCategory {
    let name: String
    let icon: String
    let iconColor: Color
    let greenCount: Int
    let amberCount: Int
    let redCount: Int
    let totalTests: Int
    let isLoading: Bool
} 