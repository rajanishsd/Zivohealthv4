import SwiftUI

/// Level 1 Card: Shows aggregated nutrition for a meal type
struct MealTypeCard: View {
    let group: MealTypeGroup
    let onTap: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with meal type
            HStack(spacing: 12) {
                Text(group.mealType.emoji)
                    .font(.system(size: 44))
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(group.mealType.displayName)
                        .font(.title3)
                        .fontWeight(.bold)
                    Text("\(group.mealCount) meal\(group.mealCount > 1 ? "s" : "")")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .font(.title3)
                    .foregroundColor(.secondary)
            }
            
            Divider()
            
            // Calories highlight
            HStack {
                Image(systemName: "flame.fill")
                    .foregroundColor(.orange)
                    .font(.title2)
                Text("\(Int(group.totalCalories))")
                    .font(.system(size: 36, weight: .bold))
                    .foregroundColor(.orange)
                Text("calories")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .padding(.leading, 4)
                Spacer()
            }
            
            // Macronutrients grid
            HStack(spacing: 0) {
                macroColumn("Protein", value: group.totalProtein, unit: "g", color: .red)
                macroColumn("Carbs", value: group.totalCarbs, unit: "g", color: .blue)
                macroColumn("Fat", value: group.totalFat, unit: "g", color: .yellow)
                macroColumn("Fiber", value: group.totalFiber, unit: "g", color: .green)
            }
            
            // Tap to view details hint
            HStack {
                Spacer()
                Text("Tap to view details")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Image(systemName: "hand.tap.fill")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            .padding(.top, 4)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.08), radius: 4, x: 0, y: 2)
        .onTapGesture {
            onTap()
        }
    }
    
    private func macroColumn(_ name: String, value: Double, unit: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(name)
                .font(.caption)
                .foregroundColor(.secondary)
            Text(String(format: "%.1f%@", value, unit))
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity)
    }
}

