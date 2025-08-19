import SwiftUI

struct FoodImageViewer: View {
    let meal: NutritionDataResponse
    @Environment(\.presentationMode) var presentationMode
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                if meal.dataSource == .photoAnalysis, let imageUrl = meal.imageUrl, !imageUrl.isEmpty {
                    // Image view for photo analysis entries
                    imageView(imageUrl: imageUrl)
                } else {
                    // Manual entry view
                    manualEntryView
                }
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
    
    private func imageView(imageUrl: String) -> some View {
        ScrollView {
            VStack(spacing: 20) {
                // Meal info header
                mealInfoHeader
                
                // Image
                AsyncImage(url: URL(string: imageUrl)) { image in
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .cornerRadius(12)
                        .shadow(radius: 4)
                } placeholder: {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.gray.opacity(0.2))
                        .frame(height: 300)
                        .overlay(
                            VStack {
                                ProgressView()
                                Text("Loading image...")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                    .padding(.top, 8)
                            }
                        )
                }
                .frame(maxHeight: 400)
                
                // AI Analysis info
                aiAnalysisInfo
                
                // Nutritional breakdown
                nutritionalBreakdown
                
                Spacer(minLength: 20)
            }
            .padding()
        }
    }
    
    private var manualEntryView: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Manual entry header
                VStack(spacing: 16) {
                    Image(systemName: "text.cursor")
                        .font(.system(size: 60))
                        .foregroundColor(.gray)
                    
                    Text("Manual Entry")
                        .font(.title2)
                        .fontWeight(.semibold)
                    
                    Text("This meal was entered manually without a photo")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 40)
                
                // Meal info
                mealInfoHeader
                
                // Nutritional breakdown
                nutritionalBreakdown
                
                Spacer(minLength: 20)
            }
            .padding()
        }
    }
    
    private var mealInfoHeader: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Meal type and time
            HStack {
                HStack(spacing: 6) {
                    Text(meal.mealType.emoji)
                        .font(.title3)
                    Text(meal.mealType.displayName)
                        .font(.headline)
                        .fontWeight(.semibold)
                }
                
                Spacer()
                
                if let mealDateTime = meal.mealDateTime {
                    Text(mealDateTime, style: .time)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            
            // Dish name
            Text(meal.displayName)
                .font(.title2)
                .fontWeight(.medium)
            
            // Dish type and serving
            HStack {
                if let dishType = meal.dishType {
                    HStack(spacing: 4) {
                        Text(dishType.emoji)
                        Text(dishType.displayName)
                    }
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                }
                
                if let servingSize = meal.servingSize {
                    Text("• \(servingSize)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Text("\(Int(meal.calories)) cal")
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.orange)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(.systemGray6))
        )
    }
    
    private var aiAnalysisInfo: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "camera.fill")
                    .foregroundColor(.blue)
                Text("AI Analysis")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
            }
            
            Text("This meal was analyzed using AI from the uploaded photo")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            if let confidenceScore = meal.confidenceScore {
                HStack {
                    Text("Confidence:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(Int(confidenceScore * 100))%")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.blue)
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.blue.opacity(0.05))
        )
    }
    
    private var nutritionalBreakdown: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Nutritional Breakdown")
                .font(.headline)
                .fontWeight(.semibold)
            
            // Macronutrients
            VStack(spacing: 12) {
                nutritionRow("Calories", value: meal.calories, unit: "cal", color: .orange)
                nutritionRow("Protein", value: meal.proteinG, unit: "g", color: .red)
                nutritionRow("Carbohydrates", value: meal.carbsG, unit: "g", color: .blue)
                nutritionRow("Fat", value: meal.fatG, unit: "g", color: .yellow)
                
                if meal.fiberG > 0 {
                    nutritionRow("Fiber", value: meal.fiberG, unit: "g", color: .green)
                }
                
                if meal.sugarG > 0 {
                    nutritionRow("Sugar", value: meal.sugarG, unit: "g", color: .pink)
                }
                
                if meal.sodiumMg > 0 {
                    nutritionRow("Sodium", value: meal.sodiumMg, unit: "mg", color: .purple)
                }
            }
            
            // Notes if available
            if let notes = meal.notes, !notes.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Notes")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                    Text(notes)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.top, 8)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(.systemGray6))
        )
    }
    
    private func nutritionRow(_ label: String, value: Double, unit: String, color: Color) -> some View {
        HStack {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            
            Text(label)
                .font(.subheadline)
                .fontWeight(.medium)
            
            Spacer()
            
            Text("\(value, specifier: "%.1f") \(unit)")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
    }
} 