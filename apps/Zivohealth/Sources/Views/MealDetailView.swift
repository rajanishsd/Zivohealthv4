import SwiftUI

struct MealDetailView: View {
    let meal: NutritionDataResponse
    @Environment(\.presentationMode) var presentationMode
    @AppStorage("apiEndpoint") private var apiEndpoint = AppConfig.defaultAPIEndpoint
    @State private var presignTs: String? = nil
    @State private var resolvedURL: URL? = nil
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Header Section
                    headerSection
                    
                    // Image Section
                    imageSection
                    
                    // Macronutrients Section
                    macronutrientsSection
                    
                    // Vitamins Section
                    vitaminsSection
                    
                    // Minerals Section
                    mineralsSection
                    
                    // Additional Details Section
                    additionalDetailsSection
                    
                    Spacer(minLength: 50)
                }
                .padding()
            }
            .navigationTitle("Meal Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        presentationMode.wrappedValue.dismiss()
                    }
                }
            }
        }
    }
    
    // MARK: - Header Section
    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(meal.mealType.emoji)
                    .font(.title)
                VStack(alignment: .leading, spacing: 4) {
                    Text(meal.mealType.displayName)
                        .font(.headline)
                        .foregroundColor(.secondary)
                    if let mealTime = meal.mealDateTime {
                        Text(mealTime, style: .date)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        Text(mealTime, style: .time)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }
                Spacer()
            }
            
            Text(meal.displayName)
                .font(.title2)
                .fontWeight(.bold)
            
            if let dishType = meal.dishType {
                HStack(spacing: 6) {
                    Text(dishType.emoji)
                    Text(dishType.displayName)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            
            if let servingSize = meal.servingSize {
                Text("Serving: \(servingSize)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            // Data source badge
            HStack {
                Image(systemName: meal.dataSource == .photoAnalysis ? "camera.fill" : "text.cursor")
                    .font(.caption)
                    .foregroundColor(meal.dataSource == .photoAnalysis ? .blue : .gray)
                Text(meal.dataSource.displayName)
                    .font(.caption)
                    .foregroundColor(meal.dataSource == .photoAnalysis ? .blue : .gray)
                
                if let confidence = meal.confidenceScore, meal.dataSource == .photoAnalysis {
                    Text("• \(Int(confidence * 100))% confidence")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(meal.dataSource == .photoAnalysis ? Color.blue.opacity(0.1) : Color.gray.opacity(0.1))
            )
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    // MARK: - Image Section
    private var imageSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Food Image")
                .font(.headline)
                .fontWeight(.semibold)
            
            if let imageUrl = meal.imageUrl, !imageUrl.isEmpty {
                if imageUrl.hasPrefix("s3://") {
                    if let finalURL = resolvedURL {
                        AsyncImage(url: finalURL) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fit)
                                    .frame(maxHeight: 250)
                                    .cornerRadius(12)
                            case .failure:
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(Color.red.opacity(0.1))
                                    .frame(height: 200)
                                    .overlay(
                                        VStack(spacing: 8) {
                                            Image(systemName: "exclamationmark.triangle.fill")
                                                .font(.title2)
                                                .foregroundColor(.red)
                                            Text("Failed to load image")
                                                .font(.caption)
                                                .foregroundColor(.red)
                                        }
                                    )
                            case .empty:
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(Color.gray.opacity(0.2))
                                    .frame(height: 200)
                                    .overlay(
                                        VStack(spacing: 8) {
                                            ProgressView()
                                                .progressViewStyle(CircularProgressViewStyle())
                                            Text("Loading image...")
                                                .font(.caption)
                                                .foregroundColor(.secondary)
                                        }
                                    )
                            @unknown default:
                                RoundedRectangle(cornerRadius: 12)
                                    .fill(Color.gray.opacity(0.2))
                                    .frame(height: 200)
                            }
                        }
                    } else {
                        RoundedRectangle(cornerRadius: 12)
                            .fill(Color.gray.opacity(0.2))
                            .frame(height: 200)
                            .overlay(
                                VStack(spacing: 8) {
                                    ProgressView()
                                        .progressViewStyle(CircularProgressViewStyle())
                                    Text("Preparing image...")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            )
                    }
                } else if let fullURL = fullImageURL(from: imageUrl, ts: presignTs) {
                    AsyncImage(url: fullURL) { phase in
                        switch phase {
                        case .success(let image):
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fit)
                                .frame(maxHeight: 250)
                                .cornerRadius(12)
                        case .failure:
                            RoundedRectangle(cornerRadius: 12)
                                .fill(Color.red.opacity(0.1))
                                .frame(height: 200)
                                .overlay(
                                    VStack(spacing: 8) {
                                        Image(systemName: "exclamationmark.triangle.fill")
                                            .font(.title2)
                                            .foregroundColor(.red)
                                        Text("Failed to load image")
                                            .font(.caption)
                                            .foregroundColor(.red)
                                    }
                                )
                        case .empty:
                            RoundedRectangle(cornerRadius: 12)
                                .fill(Color.gray.opacity(0.2))
                                .frame(height: 200)
                                .overlay(
                                    VStack(spacing: 8) {
                                        ProgressView()
                                            .progressViewStyle(CircularProgressViewStyle())
                                        Text("Loading image...")
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                )
                        @unknown default:
                            RoundedRectangle(cornerRadius: 12)
                                .fill(Color.gray.opacity(0.2))
                                .frame(height: 200)
                        }
                    }
                }
                
                HStack {
                    Image(systemName: "camera.fill")
                        .font(.caption)
                        .foregroundColor(.blue)
                    Text("Analyzed by AI")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    if let confidence = meal.confidenceScore {
                        Text("• \(Int(confidence * 100))% confidence")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                }
            } else {
                HStack {
                    Image(systemName: "text.cursor")
                        .font(.title2)
                        .foregroundColor(.gray)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Manual Entry")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.primary)
                        Text("No image available")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                }
                .padding()
                .background(Color.gray.opacity(0.05))
                .cornerRadius(10)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
        .onAppear {
            if presignTs == nil {
                presignTs = String(Int(Date().timeIntervalSince1970))
            }
            Task { @MainActor in
                if resolvedURL == nil, let urlStr = meal.imageUrl, urlStr.hasPrefix("s3://"), let u = await resolveSignedURL(from: urlStr) {
                    resolvedURL = u
                }
            }
        }
    }
    
    // MARK: - Macronutrients Section
    private var macronutrientsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Macronutrients")
                .font(.headline)
                .fontWeight(.semibold)
            
            // Calories highlight - more compact
            HStack {
                Image(systemName: "flame.fill")
                    .foregroundColor(.orange)
                    .font(.title3)
                Text("Calories")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                Spacer()
                Text("\(Int(meal.calories))")
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundColor(.orange)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Color.orange.opacity(0.05))
            .cornerRadius(8)
            
            // Compact macronutrients grid - 3 columns instead of 2
            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 8) {
                compactMacroCard("Protein", value: meal.proteinG, unit: "g", color: .red)
                compactMacroCard("Carbs", value: meal.carbsG, unit: "g", color: .blue)
                compactMacroCard("Fat", value: meal.fatG, unit: "g", color: .yellow)
                compactMacroCard("Fiber", value: meal.fiberG, unit: "g", color: .green)
                compactMacroCard("Sugar", value: meal.sugarG, unit: "g", color: .pink)
                compactMacroCard("Sodium", value: meal.sodiumMg, unit: "mg", color: .purple)
            }
        }
        .padding(12)
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }
    
    // MARK: - Vitamins Section
    private var vitaminsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Vitamins")
                .font(.headline)
                .fontWeight(.semibold)
            
            if hasAnyVitamins {
                // Compact vitamins list - 2 columns with smaller cards
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 6) {
                    if let vitaminA = meal.vitaminA, vitaminA > 0 {
                        compactVitaminCard("Vitamin A", value: vitaminA, unit: "mcg", color: .orange)
                    }
                    if let vitaminC = meal.vitaminC, vitaminC > 0 {
                        compactVitaminCard("Vitamin C", value: vitaminC, unit: "mg", color: .yellow)
                    }
                    if let vitaminD = meal.vitaminD, vitaminD > 0 {
                        compactVitaminCard("Vitamin D", value: vitaminD, unit: "mcg", color: .blue)
                    }
                    if let vitaminE = meal.vitaminE, vitaminE > 0 {
                        compactVitaminCard("Vitamin E", value: vitaminE, unit: "mg", color: .green)
                    }
                    if let vitaminK = meal.vitaminK, vitaminK > 0 {
                        compactVitaminCard("Vitamin K", value: vitaminK, unit: "mcg", color: .purple)
                    }
                    if let thiamin = meal.thiamin, thiamin > 0 {
                        compactVitaminCard("B1 (Thiamin)", value: thiamin, unit: "mg", color: .red)
                    }
                    if let riboflavin = meal.riboflavin, riboflavin > 0 {
                        compactVitaminCard("B2 (Riboflavin)", value: riboflavin, unit: "mg", color: .pink)
                    }
                    if let niacin = meal.niacin, niacin > 0 {
                        compactVitaminCard("B3 (Niacin)", value: niacin, unit: "mg", color: .indigo)
                    }
                    if let vitaminB6 = meal.vitaminB6, vitaminB6 > 0 {
                        compactVitaminCard("Vitamin B6", value: vitaminB6, unit: "mg", color: .teal)
                    }
                    if let folate = meal.folate, folate > 0 {
                        compactVitaminCard("Folate", value: folate, unit: "mcg", color: .mint)
                    }
                    if let vitaminB12 = meal.vitaminB12, vitaminB12 > 0 {
                        compactVitaminCard("Vitamin B12", value: vitaminB12, unit: "mcg", color: .cyan)
                    }
                }
            } else {
                Text("No vitamin data available")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 8)
            }
        }
        .padding(12)
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }
    
    // MARK: - Minerals Section
    private var mineralsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Minerals")
                .font(.headline)
                .fontWeight(.semibold)
            
            if hasAnyMinerals {
                // Compact minerals list - 2 columns with smaller cards
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 6) {
                    if let calcium = meal.calcium, calcium > 0 {
                        compactMineralCard("Calcium", value: calcium, unit: "mg", color: .blue)
                    }
                    if let iron = meal.iron, iron > 0 {
                        compactMineralCard("Iron", value: iron, unit: "mg", color: .red)
                    }
                    if let magnesium = meal.magnesium, magnesium > 0 {
                        compactMineralCard("Magnesium", value: magnesium, unit: "mg", color: .green)
                    }
                    if let phosphorus = meal.phosphorus, phosphorus > 0 {
                        compactMineralCard("Phosphorus", value: phosphorus, unit: "mg", color: .orange)
                    }
                    if let potassium = meal.potassium, potassium > 0 {
                        compactMineralCard("Potassium", value: potassium, unit: "mg", color: .purple)
                    }
                    if let zinc = meal.zinc, zinc > 0 {
                        compactMineralCard("Zinc", value: zinc, unit: "mg", color: .yellow)
                    }
                    if let copper = meal.copper, copper > 0 {
                        compactMineralCard("Copper", value: copper, unit: "mg", color: .pink)
                    }
                    if let manganese = meal.manganese, manganese > 0 {
                        compactMineralCard("Manganese", value: manganese, unit: "mg", color: .brown)
                    }
                    if let selenium = meal.selenium, selenium > 0 {
                        compactMineralCard("Selenium", value: selenium, unit: "mcg", color: .gray)
                    }
                }
            } else {
                Text("No mineral data available")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 8)
            }
        }
        .padding(12)
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }
    
    // MARK: - Additional Details Section
    private var additionalDetailsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Additional Details")
                .font(.headline)
                .fontWeight(.semibold)
            
            VStack(spacing: 12) {
                detailRow("Portion Size", value: String(format: "%.1f %@", meal.portionSize, meal.portionUnit))
                
                if let notes = meal.notes, !notes.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Notes")
                            .font(.subheadline)
                            .fontWeight(.medium)
                        Text(notes)
                            .font(.body)
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                
                detailRow("Created", value: formatDate(meal.createdAt))
                detailRow("Last Updated", value: formatDate(meal.updatedAt))
                detailRow("Aggregation Status", value: meal.aggregationStatus.capitalized)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    // MARK: - Compact Card Helper Functions
    
    private func compactMacroCard(_ name: String, value: Double?, unit: String, color: Color) -> some View {
        VStack(spacing: 2) {
            Text(name)
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundColor(.primary)
                .lineLimit(1)
            
            Text(value != nil ? String(format: "%.1f%@", value!, unit) : "0\(unit)")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 6)
        .padding(.horizontal, 4)
        .background(color.opacity(0.1))
        .cornerRadius(6)
    }
    
    private func compactVitaminCard(_ name: String, value: Double, unit: String, color: Color) -> some View {
        HStack(spacing: 6) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            
            VStack(alignment: .leading, spacing: 1) {
                Text(name)
                    .font(.caption2)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)
                    .lineLimit(1)
                
                Text(String(format: "%.1f %@", value, unit))
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color(.systemGray5))
        .cornerRadius(6)
    }
    
    private func compactMineralCard(_ name: String, value: Double, unit: String, color: Color) -> some View {
        HStack(spacing: 6) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            
            VStack(alignment: .leading, spacing: 1) {
                Text(name)
                    .font(.caption2)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)
                    .lineLimit(1)
                
                Text(String(format: "%.1f %@", value, unit))
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color(.systemGray5))
        .cornerRadius(6)
    }
    
    // MARK: - Helper Views
    private func detailRow(_ label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.subheadline)
                .fontWeight(.medium)
        }
        .onAppear {
            if presignTs == nil {
                presignTs = String(Int(Date().timeIntervalSince1970))
            }
            Task { @MainActor in
                if resolvedURL == nil, let urlStr = meal.imageUrl, let u = await resolveSignedURL(from: urlStr) {
                    resolvedURL = u
                }
            }
        }
    }
    
    // MARK: - Helper Properties
    private var hasAnyVitamins: Bool {
        return [meal.vitaminA, meal.vitaminC, meal.vitaminD, meal.vitaminE, meal.vitaminK,
                meal.thiamin, meal.riboflavin, meal.niacin, meal.vitaminB6, meal.folate, meal.vitaminB12]
            .compactMap { $0 }
            .contains { $0 > 0 }
    }
    
    private var hasAnyMinerals: Bool {
        return [meal.calcium, meal.iron, meal.magnesium, meal.phosphorus, meal.potassium,
                meal.zinc, meal.copper, meal.manganese, meal.selenium]
            .compactMap { $0 }
            .contains { $0 > 0 }
    }
    
    // MARK: - Helper Functions
    private func formatDate(_ dateString: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        
        if let date = formatter.date(from: dateString) {
            let displayFormatter = DateFormatter()
            displayFormatter.dateStyle = .medium
            displayFormatter.timeStyle = .short
            return displayFormatter.string(from: date)
        }
        
        return dateString
    }
    
    // Helper function to construct full image URL
    private func fullImageURL(from imageUrl: String?, ts: String?) -> URL? {
        guard let imageUrl = imageUrl, !imageUrl.isEmpty else {
            return nil
        }
        
        // If it's an S3 URI, use backend presign redirect endpoint for secure access.
        // Include api_key query for auth since AsyncImage cannot attach headers.
        if imageUrl.hasPrefix("s3://") {
            let encoded = imageUrl.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? imageUrl
            let apiKey = NetworkService.shared.authHeaders(requiresAuth: false)["X-API-Key"] ?? ""
            let keyParam = apiKey.isEmpty ? "" : "&api_key=\(apiKey)"
            let tsVal = ts ?? String(Int(Date().timeIntervalSince1970))
            let message = imageUrl + "." + tsVal
            let secret = NetworkService.shared.appSecretForSigning()
            let sig = NetworkService.shared.hmacSHA256Hex(message: message, secret: secret)
            return URL(string: "\(apiEndpoint)/api/v1/files/s3presign?s3_uri=\(encoded)\(keyParam)&ts=\(tsVal)&sig=\(sig)")
        }
        
        // If it's already a full URL, return it as is
        if imageUrl.hasPrefix("http://") || imageUrl.hasPrefix("https://") {
            return URL(string: imageUrl)
        }
        
        // If it's a relative path, construct full URL
        let baseURL = apiEndpoint
        let cleanPath = imageUrl.hasPrefix("/") ? String(imageUrl.dropFirst()) : imageUrl
        let fullURL = "\(baseURL)/\(cleanPath)"
        
        return URL(string: fullURL)
    }

    private func resolveSignedURL(from imageUrl: String) async -> URL? {
        guard imageUrl.hasPrefix("s3://") else { return URL(string: imageUrl) }
        let encoded = imageUrl.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? imageUrl
        let apiKey = NetworkService.shared.authHeaders(requiresAuth: false)["X-API-Key"] ?? ""
        let keyParam = apiKey.isEmpty ? "" : "&api_key=\(apiKey)"
        let tsVal = presignTs ?? String(Int(Date().timeIntervalSince1970))
        let message = imageUrl + "." + tsVal
        let secret = NetworkService.shared.appSecretForSigning()
        let sig = NetworkService.shared.hmacSHA256Hex(message: message, secret: secret)
        let urlStr = "\(apiEndpoint)/api/v1/files/s3presign?s3_uri=\(encoded)\(keyParam)&ts=\(tsVal)&sig=\(sig)&format=url"
        guard let url = URL(string: urlStr) else { return nil }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        do {
            let (data, response) = try await URLSession.shared.data(for: req)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { return nil }
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let final = json["url"] as? String {
                return URL(string: final)
            }
        } catch {
            return nil
        }
        return nil
    }
} 